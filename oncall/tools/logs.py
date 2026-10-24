"""search_logs tool: queries OpenSearch, normalises log lines into clusters, and extracts citable evidence."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal

from oncall.models import Evidence, ToolResult, make_error, make_result
from oncall.safety.exclusions import is_excluded
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

# Output budget: the agent's LLM has a small context, so keep results compact.
MAX_GROUPS = 10
MAX_LINE_CHARS = 120
MAX_EVIDENCE_TEXT = 200
UNATTRIBUTED = "unattributed"


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

    # 2. Service name: the demo's OpenSearch keeps resource attributes as literal
    # dotted keys (resource["service.name"]); older shapes nest them under
    # resource.attributes or flatten them.
    resource = (
        source.get("resource") if isinstance(source.get("resource"), dict) else {}
    )
    res_attrs = resource.get("attributes")
    if not isinstance(res_attrs, dict):
        res_attrs = {}
    res_service = resource.get("service")

    attrs = (
        source.get("attributes") if isinstance(source.get("attributes"), dict) else {}
    )

    service = (
        resource.get("service.name")
        or (res_service.get("name") if isinstance(res_service, dict) else None)
        or source.get("resource.attributes.service.name")
        or res_attrs.get("service.name")
        or res_attrs.get("service_name")
        or attrs.get("service.name")
        or attrs.get("service_name")
        or source.get("service_name")
        or source.get("service.name")
        or source.get("service")
        or source.get("app")
        or source.get("container_name")
        or UNATTRIBUTED
    )

    # 3. Log level extraction (supporting severity_number, severity_text, level, and aliases)
    severity = source.get("severity")
    sev_num = (
        severity.get("number")
        if isinstance(severity, dict)
        else source.get("severity_number")
    )
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
            or (severity.get("text") if isinstance(severity, dict) else severity)
            or "unknown"
        )

    # 4. Timestamp extraction (supporting ISO strings and unix nanoseconds)
    ts = (
        source.get("@timestamp")
        or source.get("timestamp")
        or source.get("time")
        or source.get("observed_timestamp")
        or source.get("observedTimestamp")
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
    description="Search logs, grouped into message patterns.",
    params={
        "properties": {
            "service": {
                "type": "string",
            },
            "level": {
                "type": "string",
                "enum": ["error", "warn", "info"],
                "default": "error",
            },
            "since_min": {
                "type": "integer",
                "default": 15,
            },
            "contains": {
                "type": "string",
            },
            "limit": {
                "type": "integer",
                "default": 200,
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

        if is_excluded(hit_service) or not _matches_level(hit_lvl, level):
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

    top = sorted_groups[:MAX_GROUPS]
    total = sum(info["count"] for info in groups.values())
    scope = f"service='{service}' " if service else ""
    more = " (newest only: limit reached)" if len(raw_logs) >= limit else ""
    header = (
        f"{total} log lines{more} {scope}level>='{level}' in the last "
        f"{since_min}m, {len(groups)} patterns (top {len(top)}):"
    )
    summary_lines = [header]
    evidence_list: list[Evidence] = []
    for rank, (_pattern, info) in enumerate(top, 1):
        svc = info["service"]
        first_line = " ".join(info["first_line"].split())
        if len(first_line) > MAX_LINE_CHARS:
            first_line = first_line[: MAX_LINE_CHARS - 3] + "..."
        summary_lines.append(f"x{info['count']} [{svc}] {first_line}")
        ts = info["first_ts"]
        evidence_list.append(
            {
                "id": f"log:{svc}:{rank}@{ts}",
                "text": f"x{info['count']} [{svc}] "
                + " ".join(info["first_line"].split())[:MAX_EVIDENCE_TEXT],
                "ts": ts,
            }
        )

    return make_result(
        "search_logs", query_params, "\n".join(summary_lines), evidence_list
    )
