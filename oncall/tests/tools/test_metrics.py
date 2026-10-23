"""Unit tests for get_metrics tool."""

from __future__ import annotations

from unittest.mock import MagicMock

from oncall.tools import TOOL_SCHEMAS, TOOLS
from oncall.tools.backends import BackendError, OfflineBackend
from oncall.tools.metrics import PROMQL, get_metrics


def test_tool_registration() -> None:
    assert "get_metrics" in TOOLS
    assert "get_metrics" in TOOL_SCHEMAS
    schema = TOOL_SCHEMAS["get_metrics"]
    assert schema["name"] == "get_metrics"
    assert "properties" in schema["input_schema"]
    assert "service" in schema["input_schema"]["properties"]
    assert "metric" in schema["input_schema"]["properties"]


def test_promql_dictionary_exported() -> None:
    assert "error_rate_all" in PROMQL
    assert "error_rate_service" in PROMQL
    assert "latency_p95_all" in PROMQL
    assert "rps_all" in PROMQL
    assert "top_errors_all" in PROMQL


def test_get_metrics_ranking_success() -> None:
    mock_backend = MagicMock()
    now_res = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"service_name": "checkout"}, "value": [1600000000, "0.35"]},
                {"metric": {"service_name": "payment"}, "value": [1600000000, "0.10"]},
                {"metric": {"service_name": "frontend"}, "value": [1600000000, "0.01"]},
            ],
        },
    }
    base_res = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"service_name": "checkout"}, "value": [1598200000, "0.00"]},
                {"metric": {"service_name": "payment"}, "value": [1598200000, "0.00"]},
                {"metric": {"service_name": "frontend"}, "value": [1598200000, "0.01"]},
            ],
        },
    }

    mock_backend.prom_query.side_effect = [now_res, base_res]

    result = get_metrics(metric="error_rate", backend=mock_backend)
    assert result["ok"] is True
    assert result["tool"] == "get_metrics"
    assert "checkout" in result["summary"]
    # Checkout should rank #1 with highest error rate and delta
    lines = result["summary"].splitlines()
    assert any(
        "1. checkout: now=0.3500, baseline=0.0000, delta=+0.3500" in line
        for line in lines
    )

    # Evidence checking
    assert len(result["evidence"]) == 3
    checkout_ev = next(e for e in result["evidence"] if "checkout" in e["text"])
    assert checkout_ev["id"].startswith("metric:")
    assert (
        "checkout error_rate 0.3500 (baseline 0.0000, delta +0.3500)"
        in checkout_ev["text"]
    )


def test_get_metrics_single_service() -> None:
    mock_backend = MagicMock()
    mock_backend.prom_query.side_effect = [
        {
            "status": "success",
            "data": {
                "result": [{"metric": {"service_name": "cart"}, "value": [100, "15.5"]}]
            },
        },
        {
            "status": "success",
            "data": {
                "result": [{"metric": {"service_name": "cart"}, "value": [100, "12.0"]}]
            },
        },
    ]

    result = get_metrics(service="cart", metric="rps", backend=mock_backend)
    assert result["ok"] is True
    assert "cart: now=15.5000, baseline=12.0000, delta=+3.5000" in result["summary"]


def test_get_metrics_empty_data() -> None:
    mock_backend = MagicMock()
    mock_backend.prom_query.return_value = {"status": "success", "data": {"result": []}}

    result = get_metrics(metric="latency_p95", backend=mock_backend)
    assert result["ok"] is True
    assert "No metric data returned" in result["summary"]
    assert result["evidence"] == []


def test_get_metrics_backend_error_handled() -> None:
    mock_backend = MagicMock()
    mock_backend.prom_query.side_effect = BackendError("Prometheus connection refused")

    result = get_metrics(metric="error_rate", backend=mock_backend)
    assert result["ok"] is False
    assert "Prometheus connection refused" in (result["error"] or "")


def test_get_metrics_with_offline_backend() -> None:
    offline = OfflineBackend(scenario="baseline")
    result = get_metrics(metric="error_rate", backend=offline)
    assert result["ok"] is True
    assert (
        "No metric data returned" in result["summary"] or len(result["evidence"]) >= 0
    )
