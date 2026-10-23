from __future__ import annotations

from collections import Counter

from oncall.clients.backends import opensearch_search
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.guard import is_banned_service, is_banned_text
from oncall.tools.registry import tool


@tool(
    name="get_logs",
    description=(
        "Recent log lines of one service from OpenSearch, newest first, filtered by severity level "
        "(ERROR, WARN, INFO...). Identical messages are grouped with a count."
    ),
    params={
        "service": {"type": "string", "description": "service name, e.g. payment"},
        "window_minutes": {"type": "integer", "description": "look-back window in minutes"},
        "limit": {"type": "integer", "description": "max log lines to scan (default 20)"},
        "level": {"type": "string", "description": "severity text, default ERROR"},
    },
    required=["service", "window_minutes"],
)
def get_logs(service: str, window_minutes: int, limit: int = 20, level: str = "ERROR") -> ToolOutput:
    if is_banned_service(service):
        raise ValueError(f"service not available: {service}")
    body = {
        "size": limit,
        "sort": [{"@timestamp": "desc"}],
        "_source": ["@timestamp", "body"],
        "query": {"bool": {"filter": [
            {"range": {"@timestamp": {"gte": f"now-{window_minutes}m"}}},
            {"term": {"resource.service.name.keyword": service}},
            {"term": {"severity.text.keyword": level.upper()}},
        ]}},
    }
    hits = opensearch_search(body)["hits"]
    bodies = [str(h["_source"]["body"])[:300] for h in hits["hits"]]
    counts = Counter(b for b in bodies if not is_banned_text(b))
    lines = [f"{n}x {m}" for m, n in counts.most_common()]
    summary = f"{service} {level.upper()} logs last {window_minutes}m: {hits['total']['value']} total, {len(counts)} distinct in newest {limit}"
    data = {
        "service": service,
        "level": level.upper(),
        "total": hits["total"]["value"],
        "messages": [{"count": n, "message": m} for m, n in counts.most_common()],
    }
    fact_summary = summary + (f"; top: {lines[0][:200]}" if lines else "")
    return ToolOutput(text="\n".join([summary, *lines]), facts=[Fact(signal=Signal.LOG, summary=fact_summary, data=data)])
