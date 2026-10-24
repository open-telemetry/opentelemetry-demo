"""Unit tests for search_logs tool, message normalisation, OTel field extraction, and offline replay."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx

from oncall.safety.exclusions import EXCLUDED_SERVICES
from oncall.tools.backends import BackendError, LiveBackend, OfflineBackend
from oncall.tools.logs import (
    MAX_EVIDENCE_TEXT,
    MAX_GROUPS,
    MAX_LINE_CHARS,
    UNATTRIBUTED,
    _extract_log_fields,
    _matches_level,
    normalize_message,
    search_logs,
)
from oncall.tools.registry import TOOL_SCHEMAS, TOOLS


def test_tool_registered():
    assert "search_logs" in TOOLS
    assert "search_logs" in TOOL_SCHEMAS
    schema = TOOL_SCHEMAS["search_logs"]
    assert schema["name"] == "search_logs"
    assert "service" in schema["input_schema"]["properties"]
    assert "level" in schema["input_schema"]["properties"]


def test_normalisation_unit_test_differing_only_by_ids():
    """Acceptance criteria: 3 lines differing only by ids -> 1 group."""
    line1 = "Failed to charge credit card for order 10042 user 550e8400-e29b-41d4-a716-446655440000 at 2026-10-23T15:00:00Z from 192.168.1.5"
    line2 = "Failed to charge credit card for order 10099 user 6ba7b810-9dad-11d1-80b4-00c04fd430c8 at 2026-10-23T15:01:30Z from 10.0.0.12"
    line3 = "Failed to charge credit card for order 99999 user 123e4567-e89b-12d3-a456-426614174000 at 2026-10-23T15:02:45Z from 172.16.0.8"

    norm1 = normalize_message(line1)
    norm2 = normalize_message(line2)
    norm3 = normalize_message(line3)

    assert norm1 == norm2 == norm3
    assert "<UUID>" in norm1
    assert "<N>" in norm1
    assert "<TS>" in norm1
    assert "<IP>" in norm1


def test_matches_level_hierarchy():
    # error includes fatal and error, excludes warn and info
    assert _matches_level("error", "error") is True
    assert _matches_level("fatal", "error") is True
    assert _matches_level("critical", "error") is True
    assert _matches_level("warn", "error") is False
    assert _matches_level("info", "error") is False

    # warn includes warn and error
    assert _matches_level("warn", "warn") is True
    assert _matches_level("warning", "warn") is True
    assert _matches_level("error", "warn") is True
    assert _matches_level("info", "warn") is False

    # info includes all
    assert _matches_level("info", "info") is True
    assert _matches_level("warn", "info") is True
    assert _matches_level("error", "info") is True


def test_extract_log_fields_real_otel_shapes():
    # Shape 1: OTel demo real format (resource.attributes['service.name'], severity_number, string body)
    hit_otel = {
        "body": "Connection refused to database on port 5432",
        "severity_number": 17,
        "severity_text": "ERROR",
        "@timestamp": "2026-10-23T15:00:00Z",
        "resource": {
            "attributes": {
                "service.name": "cartservice",
                "container.name": "cartservice",
            }
        },
    }
    svc, msg, lvl, ts = _extract_log_fields(hit_otel)
    assert svc == "cartservice"
    assert msg == "Connection refused to database on port 5432"
    assert lvl == "error"
    assert ts == "2026-10-23T15:00:00Z"

    # Shape 2: Flattened OpenSearch indexing ('resource.attributes.service.name', dict body, unix nano timestamp)
    hit_flattened = {
        "resource.attributes.service.name": "recommendationservice",
        "severity_number": 21,
        "body": {"message": "Out of memory in recommendation cache", "code": 500},
        "time_unix_nano": 1792767600000000000,
    }
    svc, msg, lvl, ts = _extract_log_fields(hit_flattened)
    assert svc == "recommendationservice"
    assert "Out of memory in recommendation cache" in msg
    assert lvl == "fatal"
    assert "2026" in ts

    # Shape 3: Direct attributes fallback
    hit_direct = {
        "attributes": {"service.name": "frontend", "level": "WARN"},
        "message": "User session timeout",
        "timestamp": "2026-10-23T15:10:00Z",
    }
    svc, msg, lvl, ts = _extract_log_fields(hit_direct)
    assert svc == "frontend"
    assert msg == "User session timeout"
    assert lvl == "warn"
    assert ts == "2026-10-23T15:10:00Z"


def test_backend_error_returns_ok_false():
    """Acceptance criteria: unknown index / no OpenSearch -> ok=False with helpful error."""
    mock_backend = MagicMock()
    mock_backend.logs_search.side_effect = BackendError(
        "OpenSearch index 'unknown' not found (HTTP 404)"
    )

    res = search_logs(service="cartservice", backend=mock_backend)
    assert res["ok"] is False
    assert res["evidence"] == []
    assert "OpenSearch index 'unknown' not found" in (res["error"] or "")


def test_offline_replay_of_recorded_baseline():
    """The recorded baseline replays for any limit/window the agent picks."""
    backend = OfflineBackend(scenario="baseline")
    res = search_logs(level="error", since_min=30, limit=50, backend=backend)
    assert res["ok"] is True
    assert res["evidence"]
    lines = res["summary"].splitlines()
    assert len(lines) <= 1 + MAX_GROUPS
    assert all(e["id"].startswith("log:") and "@" in e["id"] for e in res["evidence"])
    assert all(len(e["text"]) <= MAX_EVIDENCE_TEXT + 20 for e in res["evidence"])


REAL_SAMPLE = Path(__file__).parents[1] / "fixtures" / "opensearch" / "logs_sample.json"


def _real_docs() -> list[dict]:
    return json.loads(REAL_SAMPLE.read_text(encoding="utf-8"))


def _backend_returning(docs: list[dict]) -> MagicMock:
    backend = MagicMock()
    backend.logs_search.return_value = docs
    return backend


def test_real_opensearch_docs_parse_service_and_level():
    parsed = [_extract_log_fields(d) for d in _real_docs()]
    assert all(svc != UNATTRIBUTED for svc, _, _, _ in parsed)
    by_service = {svc: lvl for svc, _, lvl, _ in parsed}
    assert by_service["frontend"] == "error"
    assert by_service["cart"] == "info"
    assert {lvl for _, _, lvl, _ in parsed} == {"error", "warn", "info"}


def test_real_docs_filtered_by_level_threshold():
    docs = _real_docs()
    errors = search_logs(level="error", backend=_backend_returning(docs))
    warns = search_logs(level="warn", backend=_backend_returning(docs))
    assert errors["summary"].startswith("6 log lines level>='error'")
    assert "x4 [frontend] API request failed" in errors["summary"]
    assert warns["summary"].startswith("8 log lines level>='warn'")


def test_output_budget_and_unique_ids():
    docs = [
        {
            "@timestamp": "2026-10-23T19:00:00Z",
            "severity": {"text": "error", "number": 17},
            "resource": {"service.name": "cart"},
            "body": f"failure kind {chr(65 + i)} " + "x" * 400,
        }
        for i in range(25)
    ]
    res = search_logs(backend=_backend_returning(docs))
    lines = res["summary"].splitlines()
    assert len(lines) == 1 + MAX_GROUPS
    assert all(len(line) <= MAX_LINE_CHARS + 20 for line in lines[1:])
    assert len(res["evidence"]) == MAX_GROUPS
    assert all(len(e["text"]) <= MAX_EVIDENCE_TEXT + 20 for e in res["evidence"])
    ids = [e["id"] for e in res["evidence"]]
    assert len(set(ids)) == len(ids)
    assert all(ids_part.startswith("log:cart:") for ids_part in ids)


def test_excluded_services_dropped():
    docs = [
        {
            "severity": {"number": 17},
            "resource": {"service.name": name},
            "body": "boom",
        }
        for name in [*EXCLUDED_SERVICES, "cart"]
    ]
    res = search_logs(backend=_backend_returning(docs))
    assert res["summary"].startswith("1 log lines")
    for name in EXCLUDED_SERVICES:
        assert f"[{name}]" not in res["summary"]


def test_live_query_uses_severity_number_and_service_keyword(monkeypatch):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["url"] = str(request.url)
        sent["body"] = json.loads(request.content)
        return httpx.Response(200, json={"hits": {"hits": []}})

    backend = LiveBackend(
        prom_url="http://p", jaeger_url="http://j", opensearch_url="http://o"
    )
    monkeypatch.setattr(
        backend, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    backend.logs_search(service="product-catalog", level="warn", since_min=10, limit=5)
    assert sent["url"] == "http://o/otel-logs-*/_search"
    query = sent["body"]["query"]["bool"]
    assert {"term": {"resource.service.name.keyword": "product-catalog"}} in query[
        "filter"
    ]
    assert {"range": {"severity.number": {"gte": 13}}} in query["filter"]
    assert query["must_not"] == [
        {"terms": {"resource.service.name.keyword": sorted(EXCLUDED_SERVICES)}}
    ]
    assert sent["body"]["size"] == 5


def test_summary_says_when_limit_was_reached():
    docs = [
        {"severity": {"number": 17}, "resource": {"service.name": "cart"}, "body": "x"}
    ] * 3
    assert (
        "limit reached"
        in search_logs(limit=3, backend=_backend_returning(docs))["summary"]
    )
    assert (
        "limit reached"
        not in search_logs(limit=4, backend=_backend_returning(docs))["summary"]
    )
