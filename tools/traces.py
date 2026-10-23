"""query_traces(): recent error traces or slowest traces from Jaeger, as compact summaries.

Jaeger here is v2, whose classic /api/traces returns 404. The working route is the v3 API
(checked on live responses):
  GET <jaeger>/api/v3/traces?query.start_time_min=<RFC3339>&query.start_time_max=<RFC3339>
      &query.search_depth=<N>[&query.service_name=<svc>][&query.attributes={"error":"true"}]
  - both start times are required (400 otherwise); service_name is optional;
  - search_depth is the number of TRACES returned, most recent first;
  - the answer is OTLP JSON {"result": {"resourceSpans": [...]}}; spans of one trace can be
    spread over several resourceSpans blocks, so spans are grouped by traceId;
  - HTTP 404 with {"error": {"message": "No traces found"}} means "nothing matched", not a failure;
  - attributes {"error":"true"} matches spans whose status is ERROR (and only those).
Span kind is an int (1 internal, 2 server, 3 client, 4 producer, 5 consumer); status is
{} for UNSET, {"code": 1} OK, {"code": 2, "message": ...} ERROR.

Why errors are not read from the status alone: a failing dependency is not always marked.
So a span also counts as erroring when it has an exception event, an error attribute, a
non-OK RPC status or an HTTP 5xx status, and `why` says which signal fired.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

from tools import sanitize
from tools.endpoints import get_endpoints
from tools.result import ToolResult, backend_error, iso, utc_now, window_dict

TOOL = "query_traces"
HTTP_TIMEOUT = 20
MAX_WINDOW_MINUTES = 60
MAX_LIMIT = 10
MIN_SAMPLE, MAX_SAMPLE = 40, 100  # how many recent traces are looked at before ranking
MAX_ERROR_SPANS = 6  # erroring spans listed per trace (the count is always given)
MAX_MESSAGE = 160
MAX_GROUPS = 5
SERVICE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
KINDS = {1: "internal", 2: "server", 3: "client", 4: "producer", 5: "consumer"}
STATUS_ERROR = {2, "STATUS_CODE_ERROR"}
RPC_OK = {"", "OK", "0", 0}


class JaegerError(Exception):
    pass


# --- fetching ---------------------------------------------------------------------------

def fetch(base_url: str, params: dict, http_get=requests.get) -> list[dict]:
    """Run one v3 trace search and return its OTLP resourceSpans blocks (maybe empty)."""
    try:
        response = http_get(f"{base_url}/api/v3/traces", params=params, timeout=HTTP_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        raise JaegerError(f"Jaeger unreachable: {type(exc).__name__}: {str(exc)[:120]}") from exc
    if response.status_code == 404 and "No traces found" in response.text:
        return []
    if not response.ok:
        raise JaegerError(f"Jaeger returned HTTP {response.status_code}: {response.text[:150]}")
    try:
        return parse_blocks(response.text)
    except ValueError as exc:
        raise JaegerError(f"could not parse Jaeger response: {exc}") from exc


def parse_blocks(text: str) -> list[dict]:
    """Read one JSON document, or several concatenated ones (streamed chunks), into resourceSpans."""
    decoder, index, blocks = json.JSONDecoder(), 0, []
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        doc, index = decoder.raw_decode(text, index)
        if not isinstance(doc, dict):
            raise ValueError("response is not a JSON object")
        if "error" in doc:
            raise ValueError(f"error body: {str(doc['error'])[:150]}")
        blocks.extend(doc.get("result", {}).get("resourceSpans", []))
    return blocks


# --- parsing ----------------------------------------------------------------------------

def _attr(entries: list[dict], key: str):
    for entry in entries:
        if entry.get("key") == key:
            return sanitize.attr_value(entry)
    return None


def flatten(blocks: list[dict]) -> dict[str, list[dict]]:
    """OTLP resourceSpans -> {trace_id: [flat span, ...]} (not yet sanitised)."""
    traces: dict[str, list[dict]] = {}
    for block in blocks:
        service = _attr(block.get("resource", {}).get("attributes", []), "service.name") or "unknown"
        for scope_block in block.get("scopeSpans", []):
            scope = scope_block.get("scope", {}).get("name", "")
            for span in scope_block.get("spans", []):
                kind = span.get("kind", 0)
                traces.setdefault(span["traceId"], []).append({
                    "trace_id": span["traceId"],
                    "span_id": span.get("spanId"),
                    "parent_id": span.get("parentSpanId") or None,
                    "service": service,
                    "scope": scope,
                    "name": span.get("name", ""),
                    "kind": KINDS.get(kind, str(kind).removeprefix("SPAN_KIND_").lower()),
                    "start_ns": int(span.get("startTimeUnixNano", 0)),
                    "end_ns": int(span.get("endTimeUnixNano", 0)),
                    "status": span.get("status") or {},
                    "attributes": span.get("attributes", []),
                    "events": span.get("events", []),
                })
    return traces


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def error_signals(span: dict) -> list[str]:
    """Every reason this span counts as erroring; empty when it looks fine."""
    why = []
    attrs = span.get("attributes", [])
    if span.get("status", {}).get("code") in STATUS_ERROR:
        why.append("status_error")
    for event in span.get("events", []):
        if event.get("name") == "exception":
            kind = _attr(event.get("attributes", []), "exception.type")
            why.append(f"exception_event({kind})" if kind else "exception_event")
            break
    if str(_attr(attrs, "error")).lower() == "true":
        why.append("error_attribute")
    if _attr(attrs, "error.type"):
        why.append(f"error.type={_attr(attrs, 'error.type')}")
    for key in ("rpc.grpc.status_code", "grpc.status_code"):
        code = _attr(attrs, key)
        if code is not None and code not in RPC_OK and _int(code) != 0:
            why.append(f"rpc_status={code}")
    code = _attr(attrs, "rpc.response.status_code")
    if code is not None and code not in RPC_OK:
        why.append(f"rpc_status={code}")
    for key in ("http.response.status_code", "http.status_code"):
        status = _int(_attr(attrs, key))
        if status is not None and status >= 500:
            why.append(f"http_status={status}")
            break
    return why


def _message(span: dict) -> str | None:
    """The status message, else the exception message from an exception event."""
    text = span.get("status", {}).get("message")
    if not text:
        for event in span.get("events", []):
            if event.get("name") == "exception":
                text = _attr(event.get("attributes", []), "exception.message")
                break
    return str(text)[:MAX_MESSAGE] if text else None


def _depths(spans: list[dict]) -> dict[str, int]:
    """Depth of each span below its trace root; a span whose parent is missing counts as a root."""
    parents = {s["span_id"]: s["parent_id"] for s in spans}
    depths: dict[str, int] = {}

    def depth(span_id: str) -> int:
        if span_id not in depths:
            parent = parents.get(span_id)
            depths[span_id] = 0 if parent not in parents else depth(parent) + 1
        return depths[span_id]

    for span_id in parents:
        depth(span_id)
    return depths


def summarise(trace_id: str, spans: list[dict]) -> dict:
    """One compact summary of a (sanitised) trace."""
    depths = _depths(spans)
    by_start = sorted(spans, key=lambda s: s["start_ns"])
    ids = {s["span_id"] for s in spans}
    roots = [s for s in by_start if s["parent_id"] not in ids]
    root = roots[0] if roots else by_start[0]
    # The longest single span, not max(end) - min(start): one service with a skewed clock
    # stretches that envelope by minutes, and some roots are zero-length markers.
    duration_ns = max(sp["end_ns"] - sp["start_ns"] for sp in spans)

    errors = []
    for span in by_start:
        why = error_signals(span)
        if why:
            errors.append({
                "service": span["service"],
                "span": span["name"],
                "kind": span["kind"],
                "why": why,
                "message": _message(span),
                "_depth": depths[span["span_id"]],
                "_marked": "status_error" in why,
            })
    deepest = max(errors, key=lambda e: (e["_depth"], e["_marked"]), default=None)

    def public(error: dict) -> dict:
        return {k: v for k, v in error.items() if not k.startswith("_") and v is not None}

    return {
        "trace_id": trace_id,
        "start": iso(datetime.fromtimestamp(by_start[0]["start_ns"] / 1e9, timezone.utc)),
        "root_service": root["service"],
        "root_operation": root["name"],
        "duration_ms": round(duration_ns / 1e6, 1),
        "span_count": len(spans),
        "error_span_count": len(errors),
        "error_spans": [public(e) for e in errors[:MAX_ERROR_SPANS]],
        "deepest_error": public(deepest) if deepest else None,
    }


def error_groups(summaries: list[dict]) -> list[dict]:
    """Count error traces by where their error starts, so one dominant cause stands out."""
    groups: dict[tuple, dict] = {}
    for s in summaries:
        d = s["deepest_error"]
        if not d:
            continue
        key = (d["service"], d["span"], d["kind"], d.get("message"))
        group = groups.setdefault(key, {
            "deepest_service": d["service"], "deepest_span": d["span"], "kind": d["kind"],
            "why": d["why"], "traces": 0, "example_trace_id": s["trace_id"],
            **({"message": d["message"]} if d.get("message") else {}),
        })
        group["traces"] += 1
    return sorted(groups.values(), key=lambda g: -g["traces"])[:MAX_GROUPS]


def _group_key(summary: dict) -> tuple:
    d = summary["deepest_error"]
    return (d["service"], d["span"], d["kind"], d.get("message"))


def pick_diverse(error_traces: list[dict], limit: int) -> list[dict]:
    """Newest trace of each failure kind, biggest kind first, then the next newest of each, and so on.

    Plain recency would let one noisy failure fill the whole limit and hide the others.
    """
    newest_first = sorted(error_traces, key=lambda s: s["start"], reverse=True)
    buckets: dict[tuple, list[dict]] = {}
    for s in newest_first:
        buckets.setdefault(_group_key(s), []).append(s)
    ordered = sorted(buckets.values(), key=lambda b: -len(b))
    picked = []
    while len(picked) < limit and any(ordered):
        for bucket in ordered:
            if bucket and len(picked) < limit:
                picked.append(bucket.pop(0))
    return picked


# --- the tool ---------------------------------------------------------------------------

def query_traces(
    service: str | None = None,
    window_minutes: int = 10,
    limit: int = 5,
    mode: str = "errors",
    base_url: str | None = None,
    http_get=requests.get,
) -> ToolResult:
    if mode not in ("errors", "slow"):
        raise ValueError("mode must be 'errors' or 'slow'")
    if not 1 <= window_minutes <= MAX_WINDOW_MINUTES:
        raise ValueError(f"window_minutes must be between 1 and {MAX_WINDOW_MINUTES}")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    if service is not None and not SERVICE_NAME.match(service):
        raise ValueError(f"invalid service name {service!r}")

    now = utc_now()
    window = window_dict(window_minutes, now)
    start = (now - timedelta(minutes=window_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    depth = min(MAX_SAMPLE, max(MIN_SAMPLE, limit * 10))

    base = {"query.start_time_min": start, "query.start_time_max": end, "query.search_depth": depth}
    if service:
        base["query.service_name"] = service
    searches = [base]
    if mode == "errors":
        # Second search: only traces with a span whose status is ERROR. The first (unfiltered)
        # sample still runs because failures are not always marked as errors.
        searches.append({**base, "query.attributes": json.dumps({"error": "true"})})
    queries = [f"GET /api/v3/traces?{urlencode(p)}" for p in searches]

    if service and sanitize.is_blocked_name(service):
        return ToolResult(TOOL, "no_data", queries, window, notes=["no traces for this service"])

    if base_url is None:
        base_url = get_endpoints()["jaeger"].url
    try:
        blocks = [b for params in searches for b in fetch(base_url, params, http_get)]
    except JaegerError as exc:
        return backend_error(TOOL, queries, window, str(exc))

    removed = 0
    summaries = []
    for trace_id, spans in flatten(blocks).items():
        # The same span can come back from both searches; keep one copy.
        unique = list({s["span_id"]: s for s in spans}.values())
        kept, count = sanitize.clean_spans(unique)
        removed += count
        if kept:
            summaries.append(summarise(trace_id, kept))
    notes = [
        f"ranked among the {len(summaries)} most recent traces sampled"
        + (f" for service {service}" if service else ""),
        "a span counts as erroring on status ERROR, an exception event, an error attribute, a non-OK RPC status or HTTP 5xx; "
        "see `why`. A failing dependency is not always marked as an error",
    ]

    if mode == "errors":
        chosen = [s for s in summaries if s["error_span_count"]]
    else:
        chosen = sorted(summaries, key=lambda s: -s["duration_ms"])
    total = len(chosen)
    extra = {}
    if mode == "errors" and chosen:
        extra["error_groups"] = error_groups(chosen)
    # Last pass over exactly what will be returned (messages are free text).
    shown = pick_diverse(chosen, limit) if mode == "errors" else chosen[:limit]
    final, extra_removed = sanitize.clean_counted({"items": shown, "extra": extra})
    items, extra = final.get("items", []), final.get("extra", {})
    removed += extra_removed
    notes.append(sanitize.removal_note(removed))

    if not items:
        what = "error traces" if mode == "errors" else "traces"
        notes.insert(0, f"Jaeger answered but no {what} were found in this window; this is NOT a healthy signal")
        return ToolResult(TOOL, "no_data", queries, window, notes=notes)
    return ToolResult(TOOL, "data", queries, window, items=items, total_items=total, extra=extra, notes=notes)
