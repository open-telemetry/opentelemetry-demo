"""Unit tests for search_logs tool, message normalisation, and OpenSearch query handling."""

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

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


def test_extract_log_fields_formats():
    # Format A: standard OpenTelemetry collector structure
    hit_a = {
        "_source": {
            "body": "Connection refused to database",
            "service_name": "cartservice",
            "severity_text": "ERROR",
            "@timestamp": "2026-10-23T15:00:00Z",
        }
    }
    svc, msg, lvl, ts = _extract_log_fields(hit_a)
    assert svc == "cartservice"
    assert msg == "Connection refused to database"
    assert lvl == "error"
    assert ts == "2026-10-23T15:00:00Z"

    # Format B: nested attributes structure
    hit_b = {
        "_source": {
            "message": "Out of memory",
            "resource": {"attributes": {"service.name": "recommendationservice"}},
            "level": "FATAL",
            "timestamp": "2026-10-23T15:05:00Z",
        }
    }
    svc, msg, lvl, ts = _extract_log_fields(hit_b)
    assert svc == "recommendationservice"
    assert msg == "Out of memory"
    assert lvl == "fatal"
    assert ts == "2026-10-23T15:05:00Z"


def test_no_opensearch_endpoint_returns_error():
    """Acceptance criteria: no OpenSearch -> ok=False with helpful error."""
    with patch(
        "oncall.tools.logs.discover_endpoints", return_value={"opensearch": None}
    ):
        result = search_logs(service="cartservice")
        assert result["ok"] is False
        assert result["evidence"] == []
        assert "OpenSearch endpoint could not be resolved" in (result["error"] or "")


def test_opensearch_connection_error_returns_helpful_error():
    with (
        patch(
            "oncall.tools.logs.discover_endpoints",
            return_value={"opensearch": "http://localhost:9200"},
        ),
        patch("urllib.request.urlopen", side_effect=OSError("Connection refused")),
    ):
        result = search_logs(service="cartservice")
        assert result["ok"] is False
        assert "Failed to connect to OpenSearch" in (result["error"] or "")


def test_opensearch_unknown_index_returns_error():
    """Acceptance criteria: unknown index -> ok=False with helpful error."""
    err_body = json.dumps(
        {"error": {"type": "index_not_found_exception", "reason": "no such index"}}
    ).encode("utf-8")
    http_err = urllib.error.HTTPError(
        url="http://localhost:9200/_all/_search",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=BytesIO(err_body),
    )

    with (
        patch(
            "oncall.tools.logs.discover_endpoints",
            return_value={"opensearch": "http://localhost:9200"},
        ),
        patch("urllib.request.urlopen", side_effect=http_err),
    ):
        result = search_logs(service="nonexistent_index")
        assert result["ok"] is False
        assert "HTTP 404" in (result["error"] or "")
        assert "index_not_found_exception" in (result["error"] or "")


def test_search_logs_success_groups_and_evidence():
    hits = [
        {
            "_source": {
                "body": "Connection timeout to redis at host 10.0.0.1",
                "service_name": "cartservice",
                "severity_text": "ERROR",
                "@timestamp": "2026-10-23T15:00:10Z",
            }
        },
        {
            "_source": {
                "body": "Connection timeout to redis at host 10.0.0.2",
                "service_name": "cartservice",
                "severity_text": "ERROR",
                "@timestamp": "2026-10-23T15:00:12Z",
            }
        },
        {
            "_source": {
                "body": "Payment gateway 502 Bad Gateway",
                "service_name": "paymentservice",
                "severity_text": "FATAL",
                "@timestamp": "2026-10-23T15:00:15Z",
            }
        },
    ]

    response_bytes = json.dumps({"hits": {"hits": hits}}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_bytes
    mock_resp.__enter__.return_value = mock_resp

    with (
        patch(
            "oncall.tools.logs.discover_endpoints",
            return_value={"opensearch": "http://localhost:9200"},
        ),
        patch("urllib.request.urlopen", return_value=mock_resp),
    ):
        res = search_logs(service=None, level="error")

        assert res["ok"] is True
        assert res["error"] is None
        # Cartservice had 2 hits that normalize to the same IP pattern -> count 2
        assert "x2 [cartservice]" in res["summary"]
        assert "x1 [paymentservice]" in res["summary"]

        assert len(res["evidence"]) == 2
        ev_cart = next(e for e in res["evidence"] if "cartservice" in e["id"])
        assert ev_cart["id"] == "log:cartservice@2026-10-23T15:00:10Z"
        assert "Connection timeout to redis" in ev_cart["text"]
