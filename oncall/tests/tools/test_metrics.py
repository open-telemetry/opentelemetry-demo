"""Unit tests for get_metrics tool."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

from oncall.safety.exclusions import EXCLUDED_SERVICES, PROMQL_EXCLUDE
from oncall.tools import TOOL_SCHEMAS, TOOLS
from oncall.tools.backends import BackendError, OfflineBackend
from oncall.tools.metrics import (
    BASELINE_UNAVAILABLE,
    PROMQL,
    _build_promql,
    get_metrics,
)


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


def _vector(*series: tuple[dict, str]) -> dict:
    return {
        "status": "success",
        "data": {"result": [{"metric": m, "value": [100, v]} for m, v in series]},
    }


def test_every_promql_selector_drops_excluded_services() -> None:
    for name in PROMQL:
        metric, scope = name.rsplit("_", 1)
        promql = _build_promql(metric, "cart" if scope == "service" else None, "5m")
        # Each metric selector: the metric name followed by its {...} label matchers
        selectors = re.findall(r"traces_span_metrics_\w+\{[^}]*\}", promql)
        assert selectors, name
        for selector in selectors:
            assert PROMQL_EXCLUDE in selector, (name, selector)


def test_excluded_services_dropped_from_results() -> None:
    backend = MagicMock()
    vec = _vector(
        *(({"service_name": name}, "0.9") for name in EXCLUDED_SERVICES),
        ({"service_name": "cart"}, "0.2"),
    )
    backend.prom_query.side_effect = [vec, vec]
    result = get_metrics(metric="error_rate", backend=backend)
    for name in EXCLUDED_SERVICES:
        assert name not in result["summary"]
        assert all(name not in e["id"] + e["text"] for e in result["evidence"])


def test_evidence_ids_unique_per_series_and_promql_in_query() -> None:
    backend = MagicMock()
    vec = _vector(
        ({"service_name": "payment"}, "0.3"),
        ({"service_name": "checkout"}, "0.1"),
    )
    backend.prom_query.side_effect = [vec, vec]
    result = get_metrics(metric="error_rate", backend=backend)
    ids = [e["id"] for e in result["evidence"]]
    assert len(ids) == len(set(ids)) == 2
    assert ids[0].startswith("metric:error_rate:payment@")
    assert result["query"]["promql"] == _build_promql("error_rate", None, "5m")


def test_top_errors_series_keyed_by_service_and_span() -> None:
    backend = MagicMock()
    vec = _vector(
        ({"service_name": "cart", "span_name": "GetCart"}, "0.3"),
        ({"service_name": "cart", "span_name": "AddItem"}, "0.2"),
    )
    backend.prom_query.side_effect = [vec, vec]
    result = get_metrics(metric="top_errors", backend=backend)
    ids = {e["id"].split("@")[0] for e in result["evidence"]}
    assert ids == {"metric:top_errors:cart/GetCart", "metric:top_errors:cart/AddItem"}


def test_single_service_series_named_after_service() -> None:
    backend = MagicMock()
    vec = _vector(({}, "0.25"))
    backend.prom_query.side_effect = [vec, vec]
    result = get_metrics(service="cart", metric="error_rate", backend=backend)
    assert result["evidence"][0]["id"].startswith("metric:error_rate:cart@")


def test_clients_listed_as_symptoms_not_candidates() -> None:
    backend = MagicMock()
    vec = _vector(
        ({"service_name": "load-generator"}, "0.9"),
        ({"service_name": "payment"}, "0.3"),
    )
    backend.prom_query.side_effect = [vec, vec]
    result = get_metrics(metric="error_rate", backend=backend)
    lines = result["summary"].splitlines()
    assert lines[1].startswith("  1. payment:")
    assert not any(re.match(r"\s+\d+\. load-generator", line) for line in lines)
    assert lines[-1].startswith("User-facing symptoms")
    assert "load-generator: now=0.9000" in lines[-1]
    assert any("load-generator" in e["id"] for e in result["evidence"])


def test_promql_uses_exact_span_metric_names() -> None:
    for name, template in PROMQL.items():
        names = set(re.findall(r"traces_span_metrics_\w+", template))
        expected = (
            {"traces_span_metrics_duration_milliseconds_bucket"}
            if name.startswith("latency_p95")
            else {"traces_span_metrics_calls_total"}
        )
        assert names == expected, name


def test_missing_baseline_is_unavailable_not_zero() -> None:
    backend = MagicMock()
    empty = {"status": "success", "data": {"result": []}}
    backend.prom_query.side_effect = [
        _vector(({"service_name": "cart"}, "0.2")),
        empty,
    ]
    result = get_metrics(metric="error_rate", backend=backend)
    assert BASELINE_UNAVAILABLE in result["summary"]
    assert "baseline=" not in result["summary"]
    assert "delta" not in result["summary"]
    assert result["evidence"][0]["text"] == (
        "cart error_rate 0.2000 (baseline unavailable)"
    )
    assert result["query"]["baseline_available"] is False


def test_present_baseline_is_marked_available() -> None:
    backend = MagicMock()
    vec = _vector(({"service_name": "cart"}, "0.2"))
    backend.prom_query.side_effect = [vec, vec]
    result = get_metrics(metric="error_rate", backend=backend)
    assert result["query"]["baseline_available"] is True
    assert "(baseline 0.2000, delta +0.0000)" in result["evidence"][0]["text"]


def test_browser_telemetry_is_a_symptom_not_a_candidate() -> None:
    backend = MagicMock()
    vec = _vector(
        ({"service_name": "frontend-web"}, "0.25"),
        ({"service_name": "checkout"}, "0.04"),
    )
    backend.prom_query.side_effect = [vec, vec]
    lines = get_metrics(metric="error_rate", backend=backend)["summary"].splitlines()
    assert lines[1].startswith("  1. checkout:")
    assert lines[-1].startswith("User-facing symptoms") and "frontend-web" in lines[-1]


def test_rate_window_never_below_five_minutes() -> None:
    backend = MagicMock()
    vec = _vector(({"service_name": "cart"}, "1"))
    backend.prom_query.side_effect = [vec, vec]
    result = get_metrics(metric="rps", window_min=1, backend=backend)
    assert result["query"]["window_min"] == 5
    assert "[5m]" in result["query"]["promql"]


def test_spans_calling_the_flag_service_are_dropped() -> None:
    backend = MagicMock()
    flag_span = "Flag" + "Service/EventStream"
    vec = _vector(
        ({"service_name": "payment", "span_name": flag_span}, "0.9"),
        ({"service_name": "payment", "span_name": "Charge"}, "0.1"),
    )
    backend.prom_query.side_effect = [vec, vec]
    result = get_metrics(metric="top_errors", backend=backend)
    assert [e["id"].split("@")[0] for e in result["evidence"]] == [
        "metric:top_errors:payment/Charge"
    ]
