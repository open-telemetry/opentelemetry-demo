"""get_metrics tool for analyzing service golden signals and comparing against baseline."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Literal

from oncall.agent.taxonomy import CLIENT_SERVICES
from oncall.models import Evidence, ToolResult, make_error, make_result
from oncall.safety.exclusions import PROMQL_EXCLUDE, is_excluded, is_excluded_span
from oncall.tools.backends import BackendError, TelemetryBackend, get_backend
from oncall.tools.registry import register_tool

CALLS_METRIC = "traces_span_metrics_calls_total"
DURATION_METRIC = "traces_span_metrics_duration_milliseconds_bucket"
# Span-metrics rates need at least this window to be stable.
MIN_WINDOW_MIN = 5
BASELINE_UNAVAILABLE = "baseline unavailable (insufficient history)"

# Module-level PROMQL dictionary so F14 (alert detector) can reuse the exact queries.
# {exclude} drops the services and spans in oncall.safety.exclusions from every selector.
PROMQL = {
    "error_rate_all": (
        'sum by (service_name) (rate(traces_span_metrics_calls_total{{exclude},status_code="STATUS_CODE_ERROR"}[{window}])) / '
        "sum by (service_name) (rate(traces_span_metrics_calls_total{{exclude}}[{window}]))"
    ),
    "error_rate_service": (
        'sum (rate(traces_span_metrics_calls_total{service_name="{service}",{exclude},status_code="STATUS_CODE_ERROR"}[{window}])) / '
        'sum (rate(traces_span_metrics_calls_total{service_name="{service}",{exclude}}[{window}]))'
    ),
    "latency_p95_all": (
        "histogram_quantile(0.95, sum by (le, service_name) "
        "(rate(traces_span_metrics_duration_milliseconds_bucket{{exclude}}[{window}])))"
    ),
    "latency_p95_service": (
        "histogram_quantile(0.95, sum by (le) "
        '(rate(traces_span_metrics_duration_milliseconds_bucket{service_name="{service}",{exclude}}[{window}])))'
    ),
    "rps_all": (
        "sum by (service_name) (rate(traces_span_metrics_calls_total{{exclude}}[{window}]))"
    ),
    "rps_service": (
        'sum (rate(traces_span_metrics_calls_total{service_name="{service}",{exclude}}[{window}]))'
    ),
    "top_errors_all": (
        "topk(5, sum by (service_name, span_name) "
        '(rate(traces_span_metrics_calls_total{{exclude},status_code="STATUS_CODE_ERROR"}[{window}])))'
    ),
    "top_errors_service": (
        "topk(5, sum by (span_name) "
        '(rate(traces_span_metrics_calls_total{service_name="{service}",{exclude},status_code="STATUS_CODE_ERROR"}[{window}])))'
    ),
}


def _build_promql(metric: str, service: str | None, window: str) -> str:
    key = f"{metric}_{'service' if service else 'all'}"
    template = PROMQL.get(key)
    if not template:
        raise ValueError(f"Unknown metric type: {metric}")
    query = template.replace("{window}", window).replace("{exclude}", PROMQL_EXCLUDE)
    if service:
        query = query.replace("{service}", service)
    return query


def _extract_vector_results(
    data: dict[str, Any], service: str | None = None
) -> dict[str, float]:
    """Parse a Prometheus vector into {series key: value}.

    The key is "<service>" or "<service>/<span>", falling back to `service`
    when the query aggregated the service label away.
    """
    res_data = data.get("data", {})
    results = res_data.get("result", [])
    parsed: dict[str, float] = {}

    for item in results:
        labels = item.get("metric", {})
        series_service = labels.get("service_name") or service
        if is_excluded(series_service) or is_excluded_span(labels.get("span_name")):
            continue
        parts = [p for p in (series_service, labels.get("span_name")) if p]
        label_key = "/".join(parts) or labels.get("__name__") or "value"
        val_entry = item.get("value", [0, "0"])
        try:
            val = float(val_entry[1])
            if not math.isnan(val) and not math.isinf(val):
                parsed[label_key] = val
        except (ValueError, IndexError, TypeError):
            continue

    return parsed


def _is_client(key: str) -> bool:
    return key.split("/", 1)[0] in CLIENT_SERVICES


@register_tool(
    name="get_metrics",
    description=(
        "Golden signals now vs a baseline window; no service = rank all services."
    ),
    params={
        "properties": {
            "service": {
                "type": "string",
            },
            "metric": {
                "type": "string",
                "enum": ["error_rate", "latency_p95", "rps", "top_errors"],
                "default": "error_rate",
            },
            "window_min": {
                "type": "integer",
                "default": 5,
            },
            "baseline_offset_min": {
                "type": "integer",
                "default": 30,
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

    window_min = max(window_min, MIN_WINDOW_MIN)
    query_args["window_min"] = window_min
    window = f"{window_min}m"
    promql = _build_promql(metric, service, window)
    query_args["promql"] = promql

    now_dt = datetime.now(UTC)
    now_ts = now_dt.timestamp()
    iso_ts = now_dt.isoformat()
    baseline_ts = str(int(now_ts - (baseline_offset_min * 60)))

    try:
        now_resp = backend.prom_query(promql)
        base_resp = backend.prom_query(promql, at=baseline_ts)
    except BackendError as exc:
        return make_error("get_metrics", query_args, str(exc))

    now_values = _extract_vector_results(now_resp, service)
    base_values = _extract_vector_results(base_resp, service)

    # An empty baseline vector means Prometheus has no history that far back,
    # not that the value was zero.
    has_baseline = bool(base_values)
    query_args["baseline_available"] = has_baseline
    all_keys = set(now_values) | set(base_values)

    if not all_keys:
        return make_result(
            tool="get_metrics",
            query=query_args,
            summary=f"No metric data returned for {metric} (window {window}).",
            evidence=[],
        )

    stats: list[dict[str, Any]] = []
    for key in all_keys:
        curr = now_values.get(key, 0.0)
        base = base_values.get(key, 0.0) if has_baseline else None
        delta = None if base is None else curr - base
        stats.append({"key": key, "current": curr, "baseline": base, "delta": delta})

    stats.sort(key=lambda x: (x["current"], x["delta"] or 0.0), reverse=True)

    # Clients (load-generator) are symptoms, never candidates: keep them out of the ranking
    candidates = [e for e in stats if not _is_client(e["key"])][:5]
    clients = [e for e in stats if _is_client(e["key"])]

    def line(entry: dict[str, Any]) -> str:
        if entry["baseline"] is None:
            return f"{entry['key']}: now={entry['current']:.4f}"
        return (
            f"{entry['key']}: now={entry['current']:.4f}, "
            f"baseline={entry['baseline']:.4f}, delta={entry['delta']:+.4f}"
        )

    def comparison(entry: dict[str, Any]) -> str:
        if entry["baseline"] is None:
            return "baseline unavailable"
        return f"baseline {entry['baseline']:.4f}, delta {entry['delta']:+.4f}"

    header = (
        f"Metrics for {metric} (window={window}, vs baseline -{baseline_offset_min}m):"
    )
    if not has_baseline:
        header = f"Metrics for {metric} (window={window}; {BASELINE_UNAVAILABLE}):"
    summary_lines = [header]
    summary_lines += [f"  {rank}. {line(e)}" for rank, e in enumerate(candidates, 1)]
    if clients:
        summary_lines.append(
            "User-facing symptoms (clients, not root-cause candidates): "
            + "; ".join(line(e) for e in clients)
        )

    evidence_list: list[Evidence] = [
        {
            "id": f"metric:{metric}:{e['key']}@{iso_ts}",
            "text": f"{e['key']} {metric} {e['current']:.4f} ({comparison(e)})",
            "ts": iso_ts,
        }
        for e in candidates + clients
    ]

    return make_result(
        tool="get_metrics",
        query=query_args,
        summary="\n".join(summary_lines),
        evidence=evidence_list,
    )
