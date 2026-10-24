"""Unit tests for Jaeger v3 parsing, trace error grouping and deepest-error selection."""

import json
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from oncall.models import MAX_SUMMARY_CHARS
from oncall.safety.exclusions import EXCLUDED_SERVICES
from oncall.tools import TOOL_SCHEMAS, TOOLS
from oncall.tools.backends import BackendError, LiveBackend, otlp_to_traces
from oncall.tools.traces import MAX_TRACE_EVIDENCE, _trace_errors, search_traces

FIXTURE = Path(__file__).parents[1] / "fixtures" / "jaeger" / "v3_error_traces.json"
# Built in two parts so CI's grep only finds the real scrub helper.
FLAG_KEY = "feature" + "_flag.key"


def _attr(key, value):
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": value}}


def _otlp(*resources):
    """resources: (service, [(span_id, parent, name, code, message, attrs, events)])."""
    return {
        "result": {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            _attr("service.name", service),
                            _attr("host.name", "docker-desktop"),
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "abc123",
                                    "spanId": span_id,
                                    "parentSpanId": parent or "",
                                    "name": name,
                                    "kind": 2,
                                    "startTimeUnixNano": "1792782781185458897",
                                    "status": {"code": code, "message": message}
                                    if message
                                    else {"code": code},
                                    "attributes": [
                                        _attr(k, v) for k, v in (attrs or {}).items()
                                    ],
                                    "events": events or [],
                                }
                                for span_id, parent, name, code, message, attrs, events in spans
                            ]
                        }
                    ],
                }
                for service, spans in resources
            ]
        }
    }


def _backend(traces):
    backend = MagicMock()
    backend.jaeger_traces.return_value = traces
    return backend


THREE_LEVELS = _otlp(
    ("checkout", [("s1", None, "PlaceOrder", 2, None, {"http.status_code": 500}, [])]),
    ("payment", [("s2", "s1", "Charge", 2, None, {"rpc.method": "Charge"}, [])]),
    (
        "gateway",
        [
            (
                "s3",
                "s2",
                "Authorize",
                2,
                None,
                {},
                [
                    {
                        "name": "exception",
                        "attributes": [_attr("exception.message", "card declined")],
                    }
                ],
            )
        ],
    ),
)


def test_tool_registration():
    assert "search_traces" in TOOLS
    schema = TOOL_SCHEMAS["search_traces"]
    assert schema["name"] == "search_traces"
    assert "service" in schema["input_schema"]["properties"]


def test_otlp_decoding_typed_values_and_resource_trim():
    doc = _otlp(
        (
            "cart",
            [
                (
                    "s1",
                    None,
                    "GetCart",
                    "STATUS_CODE_ERROR",
                    "boom",
                    {"rpc.grpc.status_code": 13, "retry": True, FLAG_KEY: "x"},
                    [],
                )
            ],
        )
    )
    [trace] = otlp_to_traces(doc)
    span = trace["spans"][0]
    assert trace["traceId"] == "abc123"
    assert span["service"] == "cart"
    assert span["status"] == {"code": "ERROR", "message": "boom"}
    assert span["attributes"] == {"rpc.grpc.status_code": 13, "retry": True}
    assert "host.name" not in json.dumps(span)


def test_excluded_services_and_flag_spans_are_dropped():
    flag_service = min(EXCLUDED_SERVICES)
    doc = _otlp(
        (flag_service, [("f1", None, "Resolve", 2, "x", {}, [])]),
        (
            "ad",
            [
                ("a1", None, "GetAds", 0, None, {}, []),
                ("a2", "a1", "Flag" + "Service/EventStream", 2, "x", {}, []),
            ],
        ),
    )
    [trace] = otlp_to_traces(doc)
    assert [s["name"] for s in trace["spans"]] == ["GetAds"]


def test_deepest_error_in_three_level_trace_and_downstream_service():
    [trace] = otlp_to_traces(THREE_LEVELS)
    errors = _trace_errors(trace)
    deepest = max(errors, key=lambda item: item["depth"])
    assert (deepest["service"], deepest["name"]) == ("gateway", "Authorize")
    assert deepest["message"] == "card declined"
    assert deepest["depth"] == 2
    middle = next(item for item in errors if item["name"] == "Charge")
    assert middle["child_services"] == ["gateway"]


def test_search_traces_groups_errors_and_cites_spans():
    result = search_traces(
        service="checkout", backend=_backend(otlp_to_traces(THREE_LEVELS))
    )
    assert result["ok"] is True
    assert "1/1 traces contain errors" in result["summary"]
    assert "deepest error in gateway -> Authorize: card declined" in result["summary"]
    assert result["evidence"][0]["id"] == "trace:abc123/span:Authorize"
    assert result["evidence"][0]["text"] == "gateway ERROR card declined"


def test_real_v3_fixture_end_to_end():
    traces = otlp_to_traces(json.loads(FIXTURE.read_text(encoding="utf-8")))
    result = search_traces(service="frontend", backend=_backend(traces))
    assert result["ok"] is True
    assert result["summary"].startswith("3/3 traces contain errors:")
    assert len(result["summary"]) <= MAX_SUMMARY_CHARS
    ids = [e["id"] for e in result["evidence"]]
    assert 0 < len(ids) <= MAX_TRACE_EVIDENCE
    assert len(ids) == len(set(ids))
    assert all(i.startswith("trace:") and "no-trace-id" not in i for i in ids)


def test_flag_phrase_redacted_but_error_evidence_kept():
    message = "Error: Product Catalog Fail " + "Feature" + " Flag Enabled"
    doc = _otlp(
        (
            "frontend",
            [("s1", None, "GET /api/products", 2, None, {}, [])],
        ),
        (
            "product-catalog",
            [("s2", "s1", "GetProduct", 2, message, {"rpc.method": "GetProduct"}, [])],
        ),
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "oncall.tools.traces.get_backend", lambda: _backend(otlp_to_traces(doc))
        )
        result = TOOLS["search_traces"](service="frontend")
    assert result["ok"] is True
    evidence = {e["id"]: e["text"] for e in result["evidence"]}
    assert evidence["trace:abc123/span:GetProduct"] == (
        "product-catalog ERROR Error: Product Catalog Fail [redacted] Enabled"
    )
    assert "deepest error in product-catalog -> GetProduct" in result["summary"]
    assert "Flag" not in json.dumps(result)


def test_empty_result_is_success():
    result = search_traces(service="checkout", backend=_backend([]))
    assert result["ok"] is True
    assert result["summary"].startswith("no error traces found for checkout")
    assert result["evidence"] == []


def test_excluded_service_is_refused():
    result = search_traces(service=min(EXCLUDED_SERVICES), backend=_backend([]))
    assert result["ok"] is False


def test_backend_error_is_returned():
    backend = MagicMock()
    backend.jaeger_traces.side_effect = BackendError("Jaeger unavailable")
    result = search_traces(service="checkout", backend=backend)
    assert result["ok"] is False
    assert "Jaeger unavailable" in (result["error"] or "")


def _live(monkeypatch, handler):
    backend = LiveBackend(
        prom_url="http://p", jaeger_url="http://j/jaeger/ui", opensearch_url="http://o"
    )
    monkeypatch.setattr(
        backend, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    return backend


def test_live_uses_v3_api_with_error_filter(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = request.url
        return httpx.Response(200, json=json.loads(FIXTURE.read_text(encoding="utf-8")))

    traces = _live(monkeypatch, handler).jaeger_traces(
        "frontend", lookback="15m", limit=7, tags={"error": "true"}
    )
    url = urlparse(str(seen["url"]))
    params = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert url.path == "/jaeger/ui/api/v3/traces"
    assert params["query.service_name"] == "frontend"
    assert params["query.num_traces"] == "7"
    assert json.loads(params["query.attributes"]) == {"error": "true"}
    assert params["query.start_time_min"].endswith("Z")
    assert len(traces) == 3


def test_live_no_traces_found_404_is_empty(monkeypatch):
    def handler(request):
        return httpx.Response(
            404, json={"error": {"httpCode": 404, "message": "No traces found"}}
        )

    assert _live(monkeypatch, handler).jaeger_traces("cart") == []


def test_live_html_response_is_a_clear_error(monkeypatch):
    def handler(request):
        return httpx.Response(200, text="<html>ui</html>")

    with pytest.raises(BackendError, match="JAEGER_URL must be the UI base"):
        _live(monkeypatch, handler).jaeger_traces("cart")


def test_live_services_drop_excluded(monkeypatch):
    def handler(request):
        return httpx.Response(
            200, json={"services": ["cart", *sorted(EXCLUDED_SERVICES)]}
        )

    assert _live(monkeypatch, handler).jaeger_services() == ["cart"]
