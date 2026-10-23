"""Search Jaeger traces for grouped errors and their deepest failing spans."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from oncall.models import Evidence, ToolResult, make_error, make_result
from oncall.tools.backends import BackendError, TelemetryBackend, get_backend
from oncall.tools.registry import register_tool


def _tag_map(span: dict[str, Any]) -> dict[str, Any]:
    tags = span.get("tags", [])
    if isinstance(tags, dict):
        return tags
    return {
        item.get("key"): item.get("value")
        for item in tags
        if isinstance(item, dict) and item.get("key")
    }


def _span_name(span: dict[str, Any]) -> str:
    return str(span.get("operationName") or span.get("name") or "<unnamed>")


def _span_service(trace: dict[str, Any], span: dict[str, Any], fallback: str) -> str:
    processes = trace.get("processes", {})
    process = processes.get(span.get("processID"), {})
    if process.get("serviceName"):
        return str(process["serviceName"])
    tags = _tag_map(span)
    return str(tags.get("service.name") or tags.get("service") or fallback)


def _error_details(span: dict[str, Any]) -> tuple[bool, str, str]:
    tags = _tag_map(span)
    status = tags.get("otel.status_code", tags.get("status.code", tags.get("status_code")))
    status_text = str(status or "ERROR")
    status_error = str(status).upper() in {"ERROR", "STATUS_CODE_ERROR", "2"} or status == 2
    http_status = tags.get("http.status_code")
    if isinstance(http_status, int) and http_status >= 500:
        status_error = True
    error_tag = tags.get("error") is True or str(tags.get("error", "")).lower() == "true"
    message = next(
        (
            str(tags[key])
            for key in (
                "error.message",
                "exception.message",
                "message",
                "error",
                "otel.status_description",
            )
            if tags.get(key) not in (None, "", True, False)
        ),
        "error",
    )
    return status_error or error_tag, status_text, message


def _parent_map(spans: list[dict[str, Any]]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for span in spans:
        span_id = span.get("spanID") or span.get("spanId")
        for reference in span.get("references", []):
            if reference.get("refType") == "CHILD_OF" and reference.get("spanID"):
                parents[str(span_id)] = str(reference["spanID"])
                break
    return parents


def _span_timestamp(span: dict[str, Any]) -> str | None:
    start = span.get("startTime") or span.get("startTimeUnixNano")
    if start is None:
        return None
    try:
        value = float(start)
        seconds = value / 1_000_000_000 if value > 1e15 else value / 1_000
        return datetime.fromtimestamp(seconds, UTC).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return str(start)


def _depth(span_id: str, parents: dict[str, str]) -> int:
    depth = 0
    seen: set[str] = set()
    current = span_id
    while current in parents and current not in seen:
        seen.add(current)
        depth += 1
        current = parents[current]
    return depth


def _trace_errors(
    trace: dict[str, Any], requested_service: str
) -> list[dict[str, Any]]:
    spans = [span for span in trace.get("spans", []) if isinstance(span, dict)]
    parents = _parent_map(spans)
    errors: list[dict[str, Any]] = []
    for span in spans:
        is_error, status, message = _error_details(span)
        if not is_error:
            continue
        span_id = str(span.get("spanID") or span.get("spanId") or "")
        child_services = [
            _span_service(trace, child, requested_service)
            for child in spans
            if any(
                ref.get("refType") == "CHILD_OF"
                and str(ref.get("spanID")) == span_id
                for ref in child.get("references", [])
            )
        ]
        errors.append(
            {
                "span": span,
                "service": _span_service(trace, span, requested_service),
                "name": _span_name(span),
                "status": status,
                "message": message[:200],
                "depth": _depth(span_id, parents),
                "child_services": sorted(set(child_services)),
            }
        )
    return errors


@register_tool(
    name="search_traces",
    description="Find grouped trace errors and the deepest failing span in a service call chain.",
    params={
        "properties": {
            "service": {"type": "string", "description": "Service to search in Jaeger."},
            "only_errors": {
                "type": "boolean",
                "default": True,
                "description": "Search only traces Jaeger marks as containing errors.",
            },
            "limit": {
                "type": "integer",
                "default": 20,
                "description": "Maximum number of traces to inspect.",
            },
        },
        "required": ["service"],
    },
)
def search_traces(
    service: str, only_errors: bool = True, limit: int = 20
) -> ToolResult:
    """Search recent traces, grouping error spans and citing the deepest error."""
    query = {"service": service, "only_errors": only_errors, "limit": limit}
    try:
        backend: TelemetryBackend = get_backend()
        traces = backend.jaeger_traces(
            service=service,
            lookback="15m",
            limit=max(1, limit),
            tags={"error": "true"} if only_errors else None,
        )
    except BackendError as exc:
        return make_error("search_traces", query, str(exc))

    patterns: Counter[tuple[str, str, str]] = Counter()
    pattern_downstream: dict[tuple[str, str, str], set[str]] = {}
    evidence: list[Evidence] = []
    error_trace_count = 0
    for trace in traces[: max(0, limit)]:
        errors = _trace_errors(trace, service)
        if not errors:
            continue
        error_trace_count += 1
        deepest = max(errors, key=lambda item: item["depth"])
        key = (deepest["service"], deepest["name"], deepest["message"])
        patterns[key] += 1
        pattern_downstream.setdefault(key, set()).update(deepest["child_services"])
        trace_id = trace.get("traceID") or trace.get("traceId") or "<unknown>"
        for error in errors:
            span = error["span"]
            evidence.append(
                {
                    "id": f"trace:{trace_id}/span:{error['name']}",
                    "text": f"{error['service']} {error['status']} {error['message']}",
                    "ts": _span_timestamp(span),
                }
            )
            if len(evidence) >= 20:
                break
        if len(evidence) >= 20:
            break

    if not patterns:
        return make_result("search_traces", query, "no error traces found", [])

    summary_lines = [
        f"{error_trace_count}/{len(traces[: max(0, limit)])} traces contain errors:"
    ]
    for (span_service, name, message), count in patterns.most_common(5):
        downstream = pattern_downstream[(span_service, name, message)]
        suffix = f"; downstream: {', '.join(sorted(downstream))}" if downstream else ""
        summary_lines.append(
            f"{count}/{len(traces[: max(0, limit)])} traces: {span_service} -> "
            f"{name}: {message}; deepest error in {span_service}{suffix}"
        )
    return make_result("search_traces", query, "\n".join(summary_lines), evidence)
