"""search_logs tool: queries OpenSearch, normalises log lines into clusters, and extracts citable evidence."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from oncall.config import load_settings
from oncall.endpoints import discover_endpoints
from oncall.models import Evidence, ToolResult, make_error, make_result
from oncall.tools.registry import register_tool

log = logging.getLogger(__name__)

# Regular expressions for log message normalisation
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b|\b[0-9a-fA-F]{16,}\b")
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b")
_TS_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_NUM_RE = re.compile(r"\b\d+\b")

LEVEL_RANKS: dict[str, int] = {
    "trace": 5,
    "debug": 10,
    "info": 20,
    "information": 20,
    "warn": 30,
    "warning": 30,
    "error": 40,
    "err": 40,
    "fatal": 50,
    "critical": 50,
    "panic": 50,
    "severe": 50,
}

MIN_RANKS: dict[str, int] = {
    "info": 20,
    "warn": 30,
    "error": 40,
}


def normalize_message(msg: str) -> str:
    """Normalise a log line by stripping UUIDs, hex values, IPs, timestamps, and numbers."""
    s = _UUID_RE.sub("<UUID>", msg)
    s = _HEX_RE.sub("<HEX>", s)
    s = _IP_RE.sub("<IP>", s)
    s = _TS_RE.sub("<TS>", s)
    s = _NUM_RE.sub("<N>", s)
    return s.strip()


def _extract_log_fields(hit: dict[str, Any]) -> tuple[str, str, str, str]:
    """Extract (service, message, level, timestamp) from an OpenSearch hit."""
    source = hit.get("_source", {})

    # 1. Message extraction
    raw_body = source.get("body") or source.get("message") or source.get("log") or ""
    if isinstance(raw_body, dict):
        message = str(
            raw_body.get("message") or raw_body.get("body") or json.dumps(raw_body)
        )
    else:
        message = str(raw_body)

    # 2. Service name extraction
    service = (
        source.get("service_name")
        or source.get("service")
        or source.get("resource", {}).get("attributes", {}).get("service.name")
        or source.get("attributes", {}).get("service.name")
        or "unknown"
    )

    # 3. Log level extraction
    lvl = (
        source.get("severity_text")
        or source.get("level")
        or source.get("log.level")
        or source.get("log", {}).get("level")
        or "unknown"
    )

    # 4. Timestamp extraction
    ts = (
        source.get("@timestamp")
        or source.get("timestamp")
        or source.get("time")
        or hit.get("_source", {}).get("observed_timestamp")
        or datetime.now(UTC).isoformat()
    )

    return str(service), message.strip(), str(lvl).lower(), str(ts)


def _matches_level(log_level: str, min_level: str) -> bool:
    """Check if log_level satisfies min_level threshold."""
    min_rank = MIN_RANKS.get(min_level.lower(), 40)
    actual_rank = LEVEL_RANKS.get(log_level.lower(), 40)  # default to error if unknown
    return actual_rank >= min_rank


@register_tool(
    name="search_logs",
    description="Search service logs in OpenSearch, normalising and clustering similar error messages.",
    params={
        "properties": {
            "service": {
                "type": "string",
                "description": "Optional service name filter (e.g. 'cartservice', 'frontend').",
            },
            "level": {
                "type": "string",
                "enum": ["error", "warn", "info"],
                "default": "error",
                "description": "Minimum severity level threshold (error includes fatal, warn includes error).",
            },
            "since_min": {
                "type": "integer",
                "default": 15,
                "description": "Time window to search back in minutes.",
            },
            "contains": {
                "type": "string",
                "description": "Optional substring to filter messages.",
            },
            "limit": {
                "type": "integer",
                "default": 200,
                "description": "Maximum number of log entries to retrieve before clustering.",
            },
        },
        "required": [],
    },
)
def search_logs(
    service: str | None = None,
    level: Literal["error", "warn", "info"] = "error",
    since_min: int = 15,
    contains: str | None = None,
    limit: int = 200,
) -> ToolResult:
    """Query OpenSearch for logs, cluster by normalized pattern, and return top groups with evidence."""
    query_params: dict[str, Any] = {
        "service": service,
        "level": level,
        "since_min": since_min,
        "contains": contains,
        "limit": limit,
    }

    settings = load_settings()
    endpoints = discover_endpoints(settings)
    opensearch_url = endpoints.get("opensearch")

    if not opensearch_url:
        return make_error(
            "search_logs",
            query_params,
            "OpenSearch endpoint could not be resolved. Ensure the observability overlay is running.",
        )

    # Determine index to query
    index_name = settings.OPENSEARCH_LOG_INDEX or "_all"

    # Build OpenSearch search query
    now = datetime.now(UTC)
    start_time = now - timedelta(minutes=max(1, since_min))
    start_iso = start_time.isoformat()

    must_clauses: list[dict[str, Any]] = [
        {"range": {"@timestamp": {"gte": start_iso}}},
    ]

    if service:
        must_clauses.append(
            {
                "bool": {
                    "should": [
                        {"term": {"service_name": service}},
                        {"term": {"service": service}},
                        {"term": {"resource.attributes.service.name": service}},
                        {"wildcard": {"service_name": f"*{service}*"}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    if contains:
        must_clauses.append(
            {
                "bool": {
                    "should": [
                        {"match_phrase": {"body": contains}},
                        {"match_phrase": {"message": contains}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    search_body = {
        "size": min(max(1, limit), 1000),
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {"bool": {"must": must_clauses}},
    }

    url = f"{opensearch_url.rstrip('/')}/{index_name}/_search"
    req = urllib.request.Request(
        url,
        data=json.dumps(search_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="replace")
        return make_error(
            "search_logs",
            query_params,
            f"OpenSearch query failed with HTTP {exc.code}: {err_msg[:200]}",
        )
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return make_error(
            "search_logs",
            query_params,
            f"Failed to connect to OpenSearch at {opensearch_url}: {exc}",
        )

    hits = res_data.get("hits", {}).get("hits", [])
    if not hits:
        summary = (
            f"No logs found for service='{service}' level>='{level}' in the last {since_min}m."
            if service
            else f"No logs found level>='{level}' in the last {since_min}m."
        )
        return make_result("search_logs", query_params, summary, [])

    # Group and cluster logs
    groups: dict[str, dict[str, Any]] = {}
    for hit in hits:
        hit_service, hit_msg, hit_lvl, hit_ts = _extract_log_fields(hit)

        if not _matches_level(hit_lvl, level):
            continue

        normalized = normalize_message(hit_msg)
        group_key = f"[{hit_service}] {normalized}"

        if group_key not in groups:
            groups[group_key] = {
                "count": 0,
                "service": hit_service,
                "first_line": hit_msg,
                "first_ts": hit_ts,
            }
        groups[group_key]["count"] += 1

    if not groups:
        summary = (
            f"No logs matching level threshold '{level}' found in {len(hits)} entries."
        )
        return make_result("search_logs", query_params, summary, [])

    # Sort groups by frequency (highest count first)
    sorted_groups = sorted(
        groups.items(), key=lambda item: item[1]["count"], reverse=True
    )

    # Build summary: top 10 groups
    summary_lines: list[str] = []
    for _pattern, info in sorted_groups[:10]:
        svc = info["service"]
        first_line = info["first_line"].replace("\n", " ").strip()
        if len(first_line) > 120:
            first_line = first_line[:117] + "..."
        summary_lines.append(f"x{info['count']} [{svc}] {first_line}")

    summary = "\n".join(summary_lines)

    # Build evidence: citable items from top groups
    evidence_list: list[Evidence] = []
    for _pattern, info in sorted_groups[:20]:
        svc = info["service"]
        ts = info["first_ts"]
        ev_id = f"log:{svc}@{ts}"
        text_truncated = info["first_line"][:300]
        evidence_list.append({"id": ev_id, "text": text_truncated, "ts": ts})

    return make_result("search_logs", query_params, summary, evidence_list)
