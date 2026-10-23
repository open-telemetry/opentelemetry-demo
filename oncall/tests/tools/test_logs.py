"""Unit tests for search_logs tool, message normalisation, OTel field extraction, and offline replay."""

from unittest.mock import MagicMock

from oncall.tools.backends import BackendError, OfflineBackend
from oncall.tools.logs import (
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


def test_offline_backend_real_shaped_fixture_and_smaller_output():
    """Test using OfflineBackend with the real-shaped baseline fixture and smaller output guarantees."""
    backend = OfflineBackend(scenario="baseline")
    res = search_logs(
        service=None, level="error", since_min=15, limit=50, backend=backend
    )

    assert res["ok"] is True
    assert res["error"] is None

    # Cartservice had 2 log entries differing only by retry number (1/3 vs 2/3) -> grouped into 1 group with count 2
    assert "x2 [cartservice]" in res["summary"]
    # Paymentservice had 1 fatal log -> count 1
    assert "x1 [paymentservice]" in res["summary"]

    # Smaller output checks:
    summary_lines = res["summary"].splitlines()
    assert len(summary_lines) <= 5
    for line in summary_lines:
        assert len(line) <= 95

    assert len(res["evidence"]) <= 5
    for ev in res["evidence"]:
        assert len(ev["text"]) <= 160
        assert ev["id"].startswith("log:")
        assert "@" in ev["id"]
