from __future__ import annotations

from collections import Counter
from typing import Any

from oncall.clients.backends import jaeger_spans
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.guard import is_banned_service, is_banned_text, scrub
from oncall.tools.registry import tool

ERROR = 2
SCAN_TRACES = 200
KEPT_ATTRS = ("grpc.error_message", "exception.type", "exception.message", "http.status_code", "http.response.status_code")


def _attr_values(span: dict[str, Any]) -> dict[str, str]:
    pairs = list(span.get("attributes", []))
    for event in span.get("events", []):
        pairs += event.get("attributes", [])
    found = {}
    for pair in pairs:
        if pair["key"] in KEPT_ATTRS:
            value = str(next(iter(pair["value"].values())))
            if not is_banned_text(value):
                found[pair["key"]] = value[:200]
    return found


def _slim(span: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": span["service"],
        "name": span["name"],
        "span_id": span["spanId"],
        "status_message": span.get("status", {}).get("message", "")[:200],
        **_attr_values(span),
    }


def _depth(span_id: str, by_id: dict[str, dict[str, Any]]) -> int:
    depth = 0
    while by_id[span_id].get("parentSpanId") in by_id:
        span_id = by_id[span_id]["parentSpanId"]
        depth += 1
    return depth


def _analyse_trace(spans: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_id = {s["spanId"]: s for s in spans}
    errors = [s for s in spans if s.get("status", {}).get("code") == ERROR and not is_banned_service(s["service"])]
    if not errors:
        return None
    deepest = max(errors, key=lambda s: _depth(s["spanId"], by_id))
    chain, current = [], deepest
    while current is not None:
        if not is_banned_service(current["service"]) and (not chain or chain[0] != current["service"]):
            chain.insert(0, current["service"])
        current = by_id.get(current.get("parentSpanId"))
    return {
        "trace_id": deepest["traceId"],
        "chain": chain,
        "origin": _slim(deepest),
        "erroring_services": sorted({s["service"] for s in errors}),
    }


@tool(
    name="get_failed_traces",
    description=(
        "Find recent traces that contain error spans for a service. For each trace returns the call chain "
        "(root service -> ... -> deepest erroring service) and the DEEPEST erroring span with its error message. "
        "The deepest erroring span is the likely origin; services above it in the chain are usually victims. "
        "Also counts how often each service was the deepest origin across the failed traces."
    ),
    params={
        "service": {"type": "string", "description": "service whose traces to search, e.g. checkout"},
        "window_minutes": {"type": "integer", "description": "look-back window in minutes"},
        "limit": {"type": "integer", "description": "max failed traces to return (default 5)"},
    },
    required=["service", "window_minutes"],
)
def get_failed_traces(service: str, window_minutes: int, limit: int = 5) -> ToolOutput:
    if is_banned_service(service):
        raise ValueError(f"service not available: {service}")
    traces: dict[str, list[dict[str, Any]]] = {}
    # Jaeger v3 cannot filter on errors server-side; scan enough traces that rare failures are not missed.
    for span in jaeger_spans(service, window_minutes, num_traces=SCAN_TRACES):
        traces.setdefault(span["traceId"], []).append(span)
    failed = [a for a in (_analyse_trace(group) for group in traces.values()) if a]
    if not failed:
        summary = f"no failed traces for {service} in last {window_minutes}m ({len(traces)} traces scanned)"
        return ToolOutput(text=summary, facts=[Fact(signal=Signal.TRACE, summary=summary, data={"scanned": len(traces)})])
    origins = Counter(f["origin"]["service"] for f in failed)
    summary = f"{len(failed)}/{len(traces)} traces for {service} failed; deepest erroring service counts: {dict(origins)}"
    facts = [Fact(signal=Signal.TRACE, summary=summary, data={"origin_counts": dict(origins), "scanned": len(traces)})]
    lines = [summary]
    for item in failed[:limit]:
        origin = item["origin"]
        message = origin.get("grpc.error_message") or origin.get("exception.message") or origin["status_message"]
        line = f"trace {item['trace_id'][:8]} chain {' -> '.join(item['chain'])}; origin {origin['service']} span '{origin['name']}': {message[:160]}"
        lines.append(line)
        facts.append(Fact(signal=Signal.TRACE, summary=line, data=scrub(item)))
    return ToolOutput(text="\n".join(lines), facts=facts)
