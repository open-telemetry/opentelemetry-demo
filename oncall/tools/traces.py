"""Search Jaeger traces for grouped errors and their deepest failing spans."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from oncall.models import (
    MAX_SUMMARY_CHARS,
    Evidence,
    ToolResult,
    make_error,
    make_result,
)
from oncall.safety.exclusions import is_excluded, is_excluded_span
from oncall.tools.backends import BackendError, TelemetryBackend, get_backend
from oncall.tools.registry import register_tool

MAX_TRACE_EVIDENCE = 10
MAX_PATTERNS = 5
MAX_MESSAGE_CHARS = 200
MESSAGE_ATTRIBUTES = (
    "exception.message",
    "error.message",
    "grpc.error_message",
    "error.type",
)


def _http_status(attributes: dict[str, Any]) -> int | None:
    value = attributes.get(
        "http.response.status_code", attributes.get("http.status_code")
    )
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _error_details(span: dict[str, Any]) -> tuple[bool, str]:
    """(is_error, message) for a normalised span (see backends.otlp_to_traces)."""
    attributes = span.get("attributes") or {}
    status = span.get("status") or {}
    http_status = _http_status(attributes)
    is_error = status.get("code") == "ERROR" or (
        http_status is not None and http_status >= 500
    )
    exception_messages = [
        str(event["attributes"]["exception.message"])
        for event in span.get("events") or []
        if (event.get("attributes") or {}).get("exception.message")
    ]
    candidates = [
        status.get("message"),
        *exception_messages,
        *(attributes.get(key) for key in MESSAGE_ATTRIBUTES),
        f"HTTP {http_status}" if http_status else None,
    ]
    message = next((str(c) for c in candidates if c not in (None, "")), "error")
    return is_error, " ".join(message.split())[:MAX_MESSAGE_CHARS]


def _span_timestamp(span: dict[str, Any]) -> str | None:
    start = span.get("startTimeUnixNano")
    if start is None:
        return None
    try:
        return datetime.fromtimestamp(int(start) / 1e9, UTC).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _depth(span_id: str, parents: dict[str, str]) -> int:
    depth = 0
    seen: set[str] = set()
    current = span_id
    while current in parents and current not in seen:
        seen.add(current)
        depth += 1
        current = parents[current]
    return depth


def _trace_errors(trace: dict[str, Any]) -> list[dict[str, Any]]:
    spans = [
        span
        for span in trace.get("spans", [])
        if isinstance(span, dict)
        and not is_excluded(span.get("service"))
        and not is_excluded_span(span.get("name"))
    ]
    parents = {
        str(s["spanId"]): str(s["parentSpanId"]) for s in spans if s.get("parentSpanId")
    }
    children: dict[str, set[str]] = {}
    for span in spans:
        if span.get("parentSpanId"):
            children.setdefault(str(span["parentSpanId"]), set()).add(
                str(span.get("service"))
            )
    errors: list[dict[str, Any]] = []
    for span in spans:
        is_error, message = _error_details(span)
        if not is_error:
            continue
        span_id = str(span.get("spanId") or "")
        errors.append(
            {
                "span": span,
                "service": str(span.get("service") or "unattributed"),
                "name": str(span.get("name") or "<unnamed>"),
                "message": message,
                "depth": _depth(span_id, parents),
                "child_services": sorted(children.get(span_id, set())),
            }
        )
    return errors


@register_tool(
    name="search_traces",
    description="Group error traces of a service and find the deepest failing span.",
    params={
        "properties": {
            "service": {
                "type": "string",
            },
            "only_errors": {
                "type": "boolean",
                "default": True,
            },
            "limit": {
                "type": "integer",
                "default": 20,
            },
        },
        "required": ["service"],
    },
)
def search_traces(
    service: str,
    only_errors: bool = True,
    limit: int = 20,
    backend: TelemetryBackend | None = None,
) -> ToolResult:
    """Search recent traces, grouping error spans and citing the deepest error."""
    query = {"service": service, "only_errors": only_errors, "limit": limit}
    if is_excluded(service):
        return make_error("search_traces", query, "service is not available to search")
    try:
        traces = (backend or get_backend()).jaeger_traces(
            service=service,
            lookback="15m",
            limit=max(1, limit),
            tags={"error": "true"} if only_errors else None,
        )
    except BackendError as exc:
        return make_error("search_traces", query, str(exc))

    inspected = traces[: max(1, limit)]
    patterns: Counter[tuple[str, str, str]] = Counter()
    pattern_downstream: dict[tuple[str, str, str], set[str]] = {}
    evidence: list[Evidence] = []
    seen_ids: set[str] = set()
    error_trace_count = 0
    for trace in inspected:
        errors = _trace_errors(trace)
        if not errors:
            continue
        error_trace_count += 1
        errors.sort(key=lambda item: item["depth"], reverse=True)
        deepest = errors[0]
        key = (deepest["service"], deepest["name"], deepest["message"])
        patterns[key] += 1
        pattern_downstream.setdefault(key, set()).update(deepest["child_services"])
        trace_id = trace.get("traceId") or "no-trace-id"
        for error in errors:
            ev_id = f"trace:{trace_id}/span:{error['name']}"
            if ev_id in seen_ids or len(evidence) >= MAX_TRACE_EVIDENCE:
                continue
            seen_ids.add(ev_id)
            evidence.append(
                {
                    "id": ev_id,
                    "text": f"{error['service']} ERROR {error['message']}",
                    "ts": _span_timestamp(error["span"]),
                }
            )

    if not patterns:
        return make_result(
            "search_traces",
            query,
            f"no error traces found for {service} in the last 15m "
            f"({len(inspected)} traces inspected)",
            [],
        )

    summary_lines = [f"{error_trace_count}/{len(inspected)} traces contain errors:"]
    for (span_service, name, message), count in patterns.most_common(MAX_PATTERNS):
        downstream = pattern_downstream[(span_service, name, message)]
        suffix = f"; downstream: {', '.join(sorted(downstream))}" if downstream else ""
        summary_lines.append(
            f"{count}/{len(inspected)} traces: deepest error in {span_service} "
            f"-> {name}: {message}{suffix}"
        )
    summary = "\n".join(summary_lines)[:MAX_SUMMARY_CHARS]
    return make_result("search_traces", query, summary, evidence)
