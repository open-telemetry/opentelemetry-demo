"""search_logs tool: queries OpenSearch, normalises log lines into clusters, and extracts citable evidence."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal

from oncall.models import Evidence, ToolResult, make_error, make_result
from oncall.tools.backends import BackendError, TelemetryBackend, get_backend
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
    """Extract (service, message, level, timestamp) from an OpenSearch log hit or _source dictionary."""
    source = hit.get("_source", hit)
    if not isinstance(source, dict):
        source = {}

    # 1. Message extraction
    raw_body = (
        source.get("body")
        or source.get("message")
        or source.get("log")
        or (
            source.get("attributes", {}).get("message")
            if isinstance(source.get("attributes"), dict)
            else None
        )
        or (
            source.get("attributes", {}).get("exception.message")
            if isinstance(source.get("attributes"), dict)
            else None
        )
        or source.get("exception.message")
        or ""
    )
    if isinstance(raw_body, dict):
        message = str(
            raw_body.get("message")
            or raw_body.get("body")
            or json.dumps(raw_body, sort_keys=True)
        )
    else:
        message = str(raw_body)

    # 2. Service name extraction (handling flattened, nested resource attributes, and container names)
    res_attrs = (
        source.get("resource", {}).get("attributes")
        if isinstance(source.get("resource"), dict)
        else {}
    )
    if not isinstance(res_attrs, dict):
        res_attrs = {}

    attrs = (
        source.get("attributes") if isinstance(source.get("attributes"), dict) else {}
    )
    if not isinstance(attrs, dict):
        attrs = {}

    service = (
        source.get("resource.attributes.service.name")
        or res_attrs.get("service.name")
        or res_attrs.get("service_name")
        or attrs.get("service.name")
        or attrs.get("service_name")
        or source.get("service_name")
        or source.get("service.name")
        or source.get("service")
        or source.get("app")
        or source.get("container_name")
        or "unknown"
    )

    # 3. Log level extraction (supporting severity_number, severity_text, level, and aliases)
    sev_num = source.get("severity_number")
    if isinstance(sev_num, int):
        if sev_num >= 21:
            lvl = "fatal"
        elif sev_num >= 17:
            lvl = "error"
        elif sev_num >= 13:
            lvl = "warn"
        elif sev_num >= 9:
            lvl = "info"
        elif sev_num >= 5:
            lvl = "debug"
        else:
            lvl = "trace"
    else:
        lvl = (
            source.get("severity_text")
            or source.get("level")
            or source.get("log.level")
            or (
                source.get("log", {}).get("level")
                if isinstance(source.get("log"), dict)
                else None
            )
            or attrs.get("level")
            or source.get("severity")
            or "unknown"
        )

    # 4. Timestamp extraction (supporting ISO strings and unix nanoseconds)
    ts = (
        source.get("@timestamp")
        or source.get("timestamp")
        or source.get("time")
        or source.get("observed_timestamp")
    )
    if not ts and "time_unix_nano" in source:
        try:
            nano = int(source["time_unix_nano"])
            ts = datetime.fromtimestamp(nano / 1e9, tz=UTC).isoformat()
        except (ValueError, TypeError, OverflowError):
            ts = None

    if not ts:
        ts = datetime.now(UTC).isoformat()

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
    backend: TelemetryBackend | None = None,
) -> ToolResult:
    """Query OpenSearch for logs, cluster by normalized pattern, and return concise top groups with evidence."""
    query_params: dict[str, Any] = {
        "service": service,
        "level": level,
        "since_min": since_min,
        "contains": contains,
        "limit": limit,
    }

    try:
        be = backend or get_backend()
        raw_logs = be.logs_search(
            service=service,
            level=level,
            since_min=since_min,
            limit=limit,
        )
    except BackendError as exc:
        return make_error("search_logs", query_params, str(exc))
    except Exception as exc:  # noqa: BLE001
        return make_error("search_logs", query_params, f"{type(exc).__name__}: {exc}")

    if not raw_logs:
        summary = (
            f"No logs found for service='{service}' level>='{level}' in the last {since_min}m."
            if service
            else f"No logs found level>='{level}' in the last {since_min}m."
        )
        return make_result("search_logs", query_params, summary, [])

    # Group and cluster logs
    groups: dict[str, dict[str, Any]] = {}
    contains_filter = contains.lower() if contains else None

    for entry in raw_logs:
        hit_service, hit_msg, hit_lvl, hit_ts = _extract_log_fields(entry)

        if not _matches_level(hit_lvl, level):
            continue

        if contains_filter and contains_filter not in hit_msg.lower():
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
        summary = f"No logs matching level threshold '{level}' found in {len(raw_logs)} entries."
        return make_result("search_logs", query_params, summary, [])

    # Sort groups by frequency (highest count first)
    sorted_groups = sorted(
        groups.items(), key=lambda item: item[1]["count"], reverse=True
    )

    # Build concise summary: top 5 groups, concise line width (smaller output)
    summary_lines: list[str] = []
    for _pattern, info in sorted_groups[:5]:
        svc = info["service"]
        first_line = info["first_line"].replace("\n", " ").strip()
        if len(first_line) > 90:
            first_line = first_line[:87] + "..."
        summary_lines.append(f"x{info['count']} [{svc}] {first_line}")

    summary = "\n".join(summary_lines)

    # Build concise evidence: top 5 items, truncated to 160 chars (smaller output)
    evidence_list: list[Evidence] = []
    for _pattern, info in sorted_groups[:5]:
        svc = info["service"]
        ts = info["first_ts"]
        ev_id = f"log:{svc}@{ts}"
        text_truncated = info["first_line"][:160]
        evidence_list.append({"id": ev_id, "text": text_truncated, "ts": ts})

    return make_result("search_logs", query_params, summary, evidence_list)
