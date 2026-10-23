"""get_metrics tool for analyzing service golden signals and comparing against baseline."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Literal

from oncall.models import Evidence, ToolResult, make_error, make_result
from oncall.tools.backends import BackendError, TelemetryBackend, get_backend
from oncall.tools.registry import register_tool

# Module-level PROMQL dictionary so F14 (alert detector) can reuse the exact queries
PROMQL = {
    "error_rate_all": (
        'sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[{window}])) / '
        "sum by (service_name) (rate(traces_span_metrics_calls_total[{window}]))"
    ),
    "error_rate_service": (
        'sum (rate(traces_span_metrics_calls_total{service_name="{service}",status_code="STATUS_CODE_ERROR"}[{window}])) / '
        'sum (rate(traces_span_metrics_calls_total{service_name="{service}"}[{window}]))'
    ),
    "latency_p95_all": (
        "histogram_quantile(0.95, sum by (le, service_name) "
        "(rate(traces_span_metrics_duration_ms_bucket[{window}])))"
    ),
    "latency_p95_service": (
        "histogram_quantile(0.95, sum by (le) "
        '(rate(traces_span_metrics_duration_ms_bucket{service_name="{service}"}[{window}])))'
    ),
    "rps_all": (
        "sum by (service_name) (rate(traces_span_metrics_calls_total[{window}]))"
    ),
    "rps_service": (
        'sum (rate(traces_span_metrics_calls_total{service_name="{service}"}[{window}]))'
    ),
    "top_errors_all": (
        "topk(5, sum by (service_name, span_name) "
        '(rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[{window}])))'
    ),
    "top_errors_service": (
        "topk(5, sum by (span_name) "
        '(rate(traces_span_metrics_calls_total{service_name="{service}",status_code="STATUS_CODE_ERROR"}[{window}])))'
    ),
}


def _build_promql(metric: str, service: str | None, window: str) -> str:
    key = f"{metric}_{'service' if service else 'all'}"
    template = PROMQL.get(key)
    if not template:
        raise ValueError(f"Unknown metric type: {metric}")
    query = template.replace("{window}", window)
    if service:
        query = query.replace("{service}", service)
    return query


def _extract_vector_results(data: dict[str, Any]) -> dict[str, float]:
    """Parse Prometheus vector query result into a dict of label/key -> float value."""
    res_data = data.get("data", {})
    results = res_data.get("result", [])
    parsed: dict[str, float] = {}

    for item in results:
        metric_labels = item.get("metric", {})
        # Use service_name or span_name or __name__
        label_key = (
            metric_labels.get("service_name")
            or metric_labels.get("span_name")
            or metric_labels.get("__name__")
            or "value"
        )
        val_entry = item.get("value", [0, "0"])
        try:
            val = float(val_entry[1])
            if not math.isnan(val) and not math.isinf(val):
                parsed[label_key] = val
        except (ValueError, IndexError, TypeError):
            continue

    return parsed


@register_tool(
    name="get_metrics",
    description=(
        "Query service golden signals (error_rate, latency_p95, rps, top_errors) "
        "and compare now vs baseline (offset window). When service is None, ranks all services."
    ),
    params={
        "properties": {
            "service": {
                "type": "string",
                "description": "Specific service to inspect. If omitted, ranks all services.",
            },
            "metric": {
                "type": "string",
                "enum": ["error_rate", "latency_p95", "rps", "top_errors"],
                "default": "error_rate",
                "description": "Golden signal metric to query.",
            },
            "window_min": {
                "type": "integer",
                "default": 5,
                "description": "Time window for rate calculations in minutes.",
            },
            "baseline_offset_min": {
                "type": "integer",
                "default": 30,
                "description": "Minutes in the past for baseline comparison window.",
            },
        },
        "required": [],
    },
)
def get_metrics(
    service: str | None = None,
    metric: Literal["error_rate", "latency_p95", "rps", "top_errors"] = "error_rate",
    window_min: int = 5,
    baseline_offset_min: int = 30,
    backend: TelemetryBackend | None = None,
) -> ToolResult:
    """Analyze service metrics comparing current values to historical baseline."""
    query_args = {
        "service": service,
        "metric": metric,
        "window_min": window_min,
        "baseline_offset_min": baseline_offset_min,
    }

    if backend is None:
        backend = get_backend()

    window = f"{window_min}m"
    promql = _build_promql(metric, service, window)

    now_dt = datetime.now(UTC)
    now_ts = now_dt.timestamp()
    iso_ts = now_dt.isoformat()
    baseline_ts = str(int(now_ts - (baseline_offset_min * 60)))

    try:
        now_resp = backend.prom_query(promql)
        base_resp = backend.prom_query(promql, at=baseline_ts)
    except BackendError as exc:
        return make_error("get_metrics", query_args, str(exc))

    now_values = _extract_vector_results(now_resp)
    base_values = _extract_vector_results(base_resp)

    # Gather all entities (services or spans)
    all_keys = set(now_values.keys()) | set(base_values.keys())

    if not all_keys:
        return make_result(
            tool="get_metrics",
            query=query_args,
            summary=f"No metric data returned for {metric} (window {window}).",
            evidence=[],
        )

    # Calculate deltas and ratios
    stats: list[dict[str, Any]] = []
    for key in all_keys:
        curr = now_values.get(key, 0.0)
        base = base_values.get(key, 0.0)
        delta = curr - base
        ratio = (curr / base) if base > 0.0 else (float("inf") if curr > 0.0 else 1.0)
        stats.append(
            {
                "key": key,
                "current": curr,
                "baseline": base,
                "delta": delta,
                "ratio": ratio,
            }
        )

    # Sort: descending by current value and delta
    stats.sort(key=lambda x: (x["current"], x["delta"]), reverse=True)

    # Build summary and evidence
    top_entries = stats[:5]
    summary_lines = [
        f"Metrics for {metric} (window={window}, vs baseline -{baseline_offset_min}m):"
    ]
    evidence_list: list[Evidence] = []

    for rank, entry in enumerate(top_entries, 1):
        key = entry["key"]
        c = entry["current"]
        b = entry["baseline"]
        d = entry["delta"]
        summary_lines.append(
            f"  {rank}. {key}: now={c:.4f}, baseline={b:.4f}, delta={d:+.4f}"
        )
        evidence_list.append(
            {
                "id": f"metric:{promql}@{iso_ts}",
                "text": f"{key} {metric} {c:.4f} (baseline {b:.4f}, delta {d:+.4f})",
                "ts": iso_ts,
            }
        )

    return make_result(
        tool="get_metrics",
        query=query_args,
        summary="\n".join(summary_lines),
        evidence=evidence_list,
    )
