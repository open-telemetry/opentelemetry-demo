"""query_logs(): top error log lines from OpenSearch, grouped, with the message text kept verbatim.

Index pattern `otel-logs-*` (one index per day). Fields (checked live):
  body                    the message (text)
  severity.text           level, NOT normalised: INFO, info, Information, error, ERROR, Error, warn ...
                          (it is a text field, so a `terms` query with lower-case values matches any case)
  observedTimestamp       when the line was seen
  resource.service.name   the service (has a .keyword sub-field)
  traceId / spanId        ids, missing on some lines

A line counts as an error when its level is error/fatal/critical-like, or when its text is
clearly an error although the level says otherwise (".NET logs 'Information', proxies log no
level at all"). Lines are grouped by (service, message) and the message is returned exactly
as stored, so it can be compared character for character later.
"""
import re

import requests

from tools import sanitize
from tools.endpoints import get_endpoints
from tools.result import ToolResult, backend_error, utc_now, window_dict

TOOL = "query_logs"
INDEX = "otel-logs-*"
HTTP_TIMEOUT = 15
MAX_WINDOW_MINUTES = 120
MAX_LIMIT = 20
FETCH = 1000  # newest matching lines read before grouping; group counts are exact only up to this
MAX_MESSAGE = 600  # a longer message is cut and flagged (`truncated`)
ERROR_LEVELS = ["error", "err", "fatal", "critical", "crit", "severe", "emergency", "alert"]
# Words that make a line an error even when its level is not (matched on the analysed text, so any case).
ERROR_WORDS = "exception failed failure fatal panic unhandled refused unavailable timeout traceback"
PLACEHOLDER = "<services excluded by the sanitiser>"
SERVICE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SOURCE_FIELDS = ["body", "severity.text", "observedTimestamp", "resource.service.name", "traceId", "spanId"]


class OpenSearchError(Exception):
    pass


def build_query(start: str, end: str, service: str | None, excluded) -> dict:
    """The exact search body. `excluded` is the list of service names to leave out."""
    filters = [
        {"range": {"observedTimestamp": {"gte": start, "lte": end}}},
        {"bool": {"minimum_should_match": 1, "should": [
            {"terms": {"severity.text": ERROR_LEVELS}},
            {"match": {"body": {"query": ERROR_WORDS, "operator": "or"}}},
        ]}},
    ]
    if service:
        filters.append({"term": {"resource.service.name.keyword": service}})
    return {
        "size": FETCH,
        "track_total_hits": True,
        "sort": [{"observedTimestamp": "desc"}],
        "_source": SOURCE_FIELDS,
        "query": {"bool": {
            "filter": filters,
            "must_not": [{"terms": {"resource.service.name.keyword": excluded}}],
        }},
    }


def search(base_url: str, body: dict, http_post=requests.post) -> dict:
    try:
        response = http_post(f"{base_url}/{INDEX}/_search", json=body, timeout=HTTP_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        raise OpenSearchError(f"OpenSearch unreachable: {type(exc).__name__}: {str(exc)[:120]}") from exc
    if not response.ok:
        raise OpenSearchError(f"OpenSearch returned HTTP {response.status_code}: {response.text[:200]}")
    try:
        answer = response.json()
        answer["hits"]["hits"]
        answer["hits"]["total"]["value"]
    except (ValueError, KeyError, TypeError) as exc:
        raise OpenSearchError(f"unexpected OpenSearch response: {type(exc).__name__}: {str(exc)[:100]}") from exc
    shards = answer.get("_shards", {})
    if answer.get("timed_out") or shards.get("failed"):
        raise OpenSearchError(f"OpenSearch search incomplete (timed_out={answer.get('timed_out')}, shards={shards})")
    return answer


def _field(node, dotted: str):
    """Read a dotted field from a hit's _source. Keys can be nested ({"resource": {"service.name": ..}}),
    fully dotted, or any mix of the two, so every split of the path is tried."""
    if not dotted:
        return node
    if not isinstance(node, dict):
        return None
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        key = ".".join(parts[:i])
        if key in node:
            found = _field(node[key], ".".join(parts[i:]))
            if found is not None:
                return found
    return None


def _millis(stamp: str) -> str:
    """'2026-10-23T17:56:20.75032228Z' -> '2026-10-23T17:56:20.750Z'. Fixed width, so strings sort as times."""
    whole, _, fraction = stamp.rstrip("Z").partition(".")
    return f"{whole}.{(fraction + '000')[:3]}Z" if whole else stamp


def to_records(hits: list[dict]) -> list[dict]:
    """Flatten OpenSearch hits into the few fields we keep. The message is not altered."""
    records = []
    for hit in hits:
        source = hit.get("_source", {})
        body = _field(source, "body")
        if not isinstance(body, str) or not body:
            continue
        level = _field(source, "severity.text")
        records.append({
            "service": _field(source, "resource.service.name") or "unknown",
            "level": level.lower() if isinstance(level, str) and level else "none",
            "time": _millis(str(_field(source, "observedTimestamp") or "")),
            "body": body,
            "trace_id": _field(source, "traceId") or None,
        })
    return records


def group(records: list[dict]) -> list[dict]:
    """Group identical (service, message) lines. Records must be newest first."""
    groups: dict[tuple, dict] = {}
    for r in records:
        g = groups.setdefault((r["service"], r["body"]), {
            "service": r["service"],
            "level": r["level"],
            "count": 0,
            "first_seen": r["time"],
            "last_seen": r["time"],
            "sample_trace_id": None,
            "message": r["body"][:MAX_MESSAGE],
            **({"truncated": True} if len(r["body"]) > MAX_MESSAGE else {}),
        })
        g["count"] += 1
        g["first_seen"] = min(g["first_seen"], r["time"])
        g["last_seen"] = max(g["last_seen"], r["time"])
        if g["sample_trace_id"] is None and r["trace_id"]:
            g["sample_trace_id"] = r["trace_id"]  # newest line that has one
    for g in groups.values():
        if g["sample_trace_id"] is None:
            del g["sample_trace_id"]
    newest_first = sorted(groups.values(), key=lambda g: g["last_seen"], reverse=True)
    return sorted(newest_first, key=lambda g: -g["count"])  # stable: ties stay newest first


def query_logs(
    service: str | None = None,
    window_minutes: int = 10,
    limit: int = 10,
    base_url: str | None = None,
    http_post=requests.post,
) -> ToolResult:
    if not 1 <= window_minutes <= MAX_WINDOW_MINUTES:
        raise ValueError(f"window_minutes must be between 1 and {MAX_WINDOW_MINUTES}")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    if service is not None and not SERVICE_NAME.match(service):
        raise ValueError(f"invalid service name {service!r}")

    now = utc_now()
    window = window_dict(window_minutes, now)
    start, end = window["start"], window["end"]
    shown_query = build_query(start, end, service, PLACEHOLDER)
    queries = [f"POST /{INDEX}/_search {shown_query}"]

    if service and sanitize.is_blocked_name(service):
        return ToolResult(TOOL, "no_data", queries, window, notes=["no log lines for this service"])

    if base_url is None:
        endpoint = get_endpoints()["opensearch"]
        if endpoint.url is None:
            return backend_error(TOOL, queries, window, f"OpenSearch address unknown: {endpoint.error}")
        base_url = endpoint.url
    body = build_query(start, end, service, sorted(sanitize.BLOCKED_SERVICES))
    try:
        answer = search(base_url, body, http_post)
    except OpenSearchError as exc:
        return backend_error(TOOL, queries, window, str(exc))

    total = answer["hits"]["total"]["value"]
    records, removed = sanitize.clean_counted(to_records(answer["hits"]["hits"]))
    notes = [
        "error lines = level error/fatal/critical-like, or text that is clearly an error whatever its level",
        f"counts cover the newest {len(answer['hits']['hits'])} of {total} matching lines",
        "lines are grouped by (service, exact message); `message` is the stored text, unaltered",
    ]
    groups = group(records)
    chosen = groups[:limit]
    # Last pass over exactly what is returned.
    cleaned, extra_removed = sanitize.clean_counted(chosen)
    notes.append(sanitize.removal_note(removed + extra_removed))

    if not cleaned:
        notes.insert(0, "OpenSearch answered but has no error lines in this window; this is NOT a healthy signal")
        return ToolResult(TOOL, "no_data", queries, window, notes=notes)
    return ToolResult(TOOL, "data", queries, window, items=cleaned, total_items=len(groups), notes=notes)
