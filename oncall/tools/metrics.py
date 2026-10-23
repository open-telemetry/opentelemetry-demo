from __future__ import annotations

from oncall.clients.backends import prom_query
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.guard import is_banned_service
from oncall.tools.registry import tool

SERVER_KINDS = 'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"'


def _by_service(expr: str) -> dict[str, float]:
    return {r["metric"]["service_name"]: float(r["value"][1]) for r in prom_query(expr)}


def _p95(window: int, offset: str = "") -> dict[str, float]:
    bucket = f"traces_span_metrics_duration_milliseconds_bucket{{{SERVER_KINDS}}}"
    expr = f"histogram_quantile(0.95, sum by (le, service_name)(rate({bucket}[{window}m]{offset})))"
    return {k: v for k, v in _by_service(expr).items() if v == v}


@tool(
    name="get_error_rates",
    description=(
        "Per-service request count, error count, error rate and p95 latency (ms) over the last N minutes, from "
        "span metrics (server-side spans only), next to the p95 of the N minutes before that as a baseline. "
        "High latency without errors suggests resource pressure. A service absent here may be down."
    ),
    params={"window_minutes": {"type": "integer", "description": "look-back window in minutes, e.g. 5"}},
    required=["window_minutes"],
)
def get_error_rates(window_minutes: int) -> ToolOutput:
    calls = f"traces_span_metrics_calls_total{{{SERVER_KINDS}}}"
    failed = f'traces_span_metrics_calls_total{{{SERVER_KINDS},status_code="STATUS_CODE_ERROR"}}'
    requests = _by_service(f"sum by (service_name)(increase({calls}[{window_minutes}m]))")
    errors = _by_service(f"sum by (service_name)(increase({failed}[{window_minutes}m]))")
    p95, baseline = _p95(window_minutes), _p95(window_minutes, f" offset {window_minutes}m")
    rows = []
    for name in sorted(requests):
        if is_banned_service(name) or requests[name] < 1:
            continue
        err = errors.get(name, 0.0)
        rows.append({
            "service": name,
            "requests": round(requests[name]),
            "errors": round(err),
            "error_rate": round(err / requests[name], 3),
            "p95_ms": round(p95.get(name, 0.0)),
            "baseline_p95_ms": round(baseline.get(name, 0.0)),
        })
    rows.sort(key=lambda r: (-r["error_rate"], -r["p95_ms"]))
    top = [f"{r['service']} err={r['error_rate']:.1%} p95={r['p95_ms']}ms (was {r['baseline_p95_ms']}ms)" for r in rows[:8]]
    summary = f"last {window_minutes}m: " + "; ".join(top)
    lines = [f"{r['service']}: req={r['requests']} err={r['errors']} rate={r['error_rate']:.1%} p95={r['p95_ms']}ms baseline_p95={r['baseline_p95_ms']}ms" for r in rows]
    return ToolOutput(text="\n".join(lines), facts=[Fact(signal=Signal.METRIC, summary=summary, data={"window_minutes": window_minutes, "services": rows})])
