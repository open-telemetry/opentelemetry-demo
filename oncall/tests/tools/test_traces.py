"""Unit tests for Jaeger trace error grouping and deepest-error selection."""

from unittest.mock import patch

from oncall.tools import TOOL_SCHEMAS, TOOLS
from oncall.tools.backends import BackendError
from oncall.tools.traces import _trace_errors, search_traces


def _span(span_id, operation, tags, parent=None):
    span = {
        "spanID": span_id,
        "operationName": operation,
        "startTime": 1700000000000,
        "tags": [{"key": key, "value": value} for key, value in tags.items()],
    }
    if parent:
        span["references"] = [{"refType": "CHILD_OF", "spanID": parent}]
    return span


def test_tool_registration():
    assert "search_traces" in TOOLS
    schema = TOOL_SCHEMAS["search_traces"]
    assert schema["name"] == "search_traces"
    assert "service" in schema["input_schema"]["properties"]


def test_deepest_error_in_three_level_trace_and_downstream_service():
    trace = {
        "traceID": "trace-123",
        "processes": {
            "root": {"serviceName": "checkout"},
            "middle": {"serviceName": "payment"},
            "deep": {"serviceName": "gateway"},
        },
        "spans": [
            _span("root-span", "checkout", {"http.status_code": 500}),
            {
                **_span("middle-span", "charge", {"error": True}, "root-span"),
                "processID": "middle",
            },
            {
                **_span(
                    "deep-span",
                    "charge-provider",
                    {"error": True, "error.message": "declined"},
                    "middle-span",
                ),
                "processID": "deep",
            },
        ],
    }

    errors = _trace_errors(trace, "checkout")
    deepest = max(errors, key=lambda item: item["depth"])
    assert deepest["service"] == "gateway"
    assert deepest["name"] == "charge-provider"
    assert deepest["message"] == "declined"
    assert deepest["depth"] == 2
    assert deepest["child_services"] == []

    middle = next(item for item in errors if item["name"] == "charge")
    assert middle["child_services"] == ["gateway"]


def test_search_traces_groups_errors_and_cites_spans():
    trace = {
        "traceID": "trace-123",
        "processes": {"p": {"serviceName": "payment"}},
        "spans": [
            _span("span-1", "charge", {"error": True, "error.message": "declined"})
        ],
    }
    backend = type("Backend", (), {"jaeger_traces": lambda self, **kwargs: [trace]})()
    with patch("oncall.tools.traces.get_backend", return_value=backend):
        result = search_traces(service="payment")

    assert result["ok"] is True
    assert "1/1 traces" in result["summary"]
    assert result["evidence"][0]["id"] == "trace:trace-123/span:charge"
    assert "declined" in result["evidence"][0]["text"]


def test_empty_result_is_success():
    backend = type("Backend", (), {"jaeger_traces": lambda self, **kwargs: []})()
    with patch("oncall.tools.traces.get_backend", return_value=backend):
        result = search_traces(service="checkout")
    assert result["ok"] is True
    assert result["summary"] == "no error traces found"
    assert result["evidence"] == []


def test_backend_error_is_returned():
    def fail(self, **kwargs):
        raise BackendError("Jaeger unavailable")

    backend = type("Backend", (), {"jaeger_traces": fail})()
    with patch("oncall.tools.traces.get_backend", return_value=backend):
        result = search_traces(service="checkout")
    assert result["ok"] is False
    assert "Jaeger unavailable" in (result["error"] or "")
