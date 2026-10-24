from __future__ import annotations

from collections import Counter

from oncall.clients.backends import opensearch_search
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.guard import is_banned_service, is_banned_text
from oncall.tools.registry import tool

# Services do not agree on severity: payment logs real failures as "warn", frontend logs
# "Checkout payment declined" as "info". So "ERROR" means: WARN or worse, OR a failure word.
FAILURE_WORDS = ("fail* OR error OR errors OR exception OR declined OR refused OR timeout OR \"timed out\" OR "
                 "unavailable OR unreachable OR panic OR fatal OR invalid OR denied OR OOM OR \"out of memory\"")
# The cause often lives in an attribute, not the body. List fields explicitly: a wildcard over
# attributes.* exceeds OpenSearch's 1024-clause limit.
DETAIL_FIELDS = ("attributes.details", "attributes.exception.message", "attributes.error")
WARN_OR_WORSE = 13  # OpenTelemetry severity numbers: 9-12 INFO, 13-16 WARN, 17-20 ERROR


def _level_filter(level: str) -> dict:
    if level in ("ERROR", "WARN"):
        return {"bool": {"should": [
            {"range": {"severity.number": {"gte": WARN_OR_WORSE}}},
            {"query_string": {"query": FAILURE_WORDS, "fields": ["body", *DETAIL_FIELDS], "lenient": True}},
        ], "minimum_should_match": 1}}
    return {"terms": {"severity.text.keyword": sorted({level, level.lower(), level.capitalize()})}}


def _detail(source: dict) -> str:
    attrs = source.get("attributes") or {}
    exception = attrs.get("exception") if isinstance(attrs.get("exception"), dict) else {}
    return str(attrs.get("details") or attrs.get("exception.message") or exception.get("message")
               or attrs.get("error") or "")[:200]


@tool(
    name="get_logs",
    description=(
        "Recent log lines of one service from OpenSearch, newest first. level=ERROR (default) returns warnings, "
        "errors and any line containing a failure word (failed, declined, refused, timeout...), because some "
        "services log real failures at INFO. Each message includes its error detail and an example trace id. "
        "Identical messages are grouped with a count."
    ),
    params={
        "service": {"type": "string", "description": "service name, e.g. payment"},
        "window_minutes": {"type": "integer", "description": "look-back window in minutes"},
        "limit": {"type": "integer", "description": "max log lines to scan (default 30)"},
        "level": {"type": "string", "description": "ERROR (default: failures of any severity) or INFO, DEBUG..."},
    },
    required=["service", "window_minutes"],
)
def get_logs(service: str, window_minutes: int, limit: int = 30, level: str = "ERROR") -> ToolOutput:
    if is_banned_service(service):
        raise ValueError(f"service not available: {service}")
    level = level.upper()
    body = {
        "size": limit,
        "sort": [{"@timestamp": "desc"}],
        "_source": ["@timestamp", "body", "severity.text", "traceId", *DETAIL_FIELDS],
        "query": {"bool": {"filter": [
            {"range": {"@timestamp": {"gte": f"now-{window_minutes}m"}}},
            {"term": {"resource.service.name.keyword": service}},
            _level_filter(level),
        ]}},
    }
    hits = opensearch_search(body)["hits"]
    counts: Counter[str] = Counter()
    examples: dict[str, dict] = {}
    for hit in hits["hits"]:
        src = hit["_source"]
        detail = _detail(src)
        message = str(src.get("body", ""))[:200] + (f" | {detail}" if detail and detail not in str(src.get("body")) else "")
        if is_banned_text(message):
            continue
        counts[message] += 1
        examples.setdefault(message, {"severity": (src.get("severity") or {}).get("text"), "trace_id": src.get("traceId")})
    lines = [f"{n}x [{examples[m]['severity']}] {m}" for m, n in counts.most_common()]
    summary = f"{service} {level} logs last {window_minutes}m: {hits['total']['value']} total, {len(counts)} distinct in newest {limit}"
    data = {
        "service": service,
        "level": level,
        "total": hits["total"]["value"],
        "messages": [{"count": n, "message": m, **examples[m]} for m, n in counts.most_common()],
    }
    fact_summary = summary + (f"; top: {lines[0][:200]}" if lines else "")
    return ToolOutput(text="\n".join([summary, *lines]), facts=[Fact(signal=Signal.LOG, summary=fact_summary, data=data)])
