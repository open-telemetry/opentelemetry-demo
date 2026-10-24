"""Shared contract types passed between tools, the agent brain and the safety module."""

import re
from typing import Literal, TypedDict

MAX_SUMMARY_CHARS = 1500
MAX_EVIDENCE_ITEMS = 20

# Matches "feature" and "flag" joined by "_", ".", "-", whitespace or nothing,
# any case (feature_flag_key, FeatureFlag.name, and span status messages such
# as "... Fail Feature Flag Enabled").
FLAG_PATTERN = re.compile(r"feature[_.\s-]?flag", re.IGNORECASE)
# The whitespace-free token around a FLAG_PATTERN match (so a label pair such as
# feature_flag_key=paymentFailure goes as a whole); FLAG_PATTERN may span one space.
FLAG_PHRASE = re.compile(r"\S*" + FLAG_PATTERN.pattern + r"\S*", re.IGNORECASE)
FLAG_REDACTED = "[redacted]"


class Evidence(TypedDict):
    id: str
    text: str
    ts: str | None


class ToolResult(TypedDict):
    tool: str
    query: dict
    summary: str
    evidence: list[Evidence]
    ok: bool
    error: str | None


class Alert(TypedDict):
    id: str
    ts: str
    service: str | None
    signal: Literal["error_rate", "latency", "container", "manual"]
    value: float | None
    threshold: float | None
    description: str
    source: Literal["detector", "manual"]


Category = Literal[
    "app_error",
    "dependency_unavailable",
    "container_down",
    "resource_cpu",
    "resource_memory",
    "network_degradation",
    "traffic_surge",
    "upstream_propagation",
    "unknown",
    "no_incident",
]


class Alternative(TypedDict):
    hypothesis: str
    rejected_because: str


class Diagnosis(TypedDict):
    component: str | None
    category: Category
    cause: str
    confidence: float
    evidence_ids: list[str]
    affected_services: list[str]
    alternatives: list[Alternative]
    decision: Literal["act", "escalate", "no_action"]
    reasoning: str


def make_result(
    tool: str, query: dict, summary: str, evidence: list[Evidence]
) -> ToolResult:
    """Build a successful ToolResult, truncating summary and evidence to the contract limits."""
    return {
        "tool": tool,
        "query": query,
        "summary": summary[:MAX_SUMMARY_CHARS],
        "evidence": list(evidence[:MAX_EVIDENCE_ITEMS]),
        "ok": True,
        "error": None,
    }


# Query keys kept in the run log but never shown to the LLM: the raw PromQL is
# long and names the excluded services in its label matchers.
LLM_HIDDEN_QUERY_KEYS = ("promql",)


def llm_query(query: dict) -> dict:
    """The part of a ToolResult's query the LLM may see."""
    return {k: v for k, v in query.items() if k not in LLM_HIDDEN_QUERY_KEYS}


def llm_view(result: ToolResult) -> dict:
    """A ToolResult as sent to the LLM (query without LLM_HIDDEN_QUERY_KEYS)."""
    return {**result, "query": llm_query(result.get("query") or {})}


def make_error(tool: str, query: dict, error: str) -> ToolResult:
    """Build a failed ToolResult with no evidence."""
    return {
        "tool": tool,
        "query": query,
        "summary": "",
        "evidence": [],
        "ok": False,
        "error": error,
    }


def scrub_flags(obj: object) -> object:
    """Remove feature-flag data (RULES.md hard rule 7) from a ToolResult or any nested value.

    Drops dict keys matching FLAG_PATTERN, drops list items shaped like an OTLP
    attribute ({"key": <match>, "value": ...}), and replaces each FLAG_PHRASE in a
    string with FLAG_REDACTED, keeping the rest of the text.
    """
    if isinstance(obj, dict):
        return {
            k: scrub_flags(v)
            for k, v in obj.items()
            if not (isinstance(k, str) and FLAG_PATTERN.search(k))
        }
    if isinstance(obj, (list, tuple)):
        return type(obj)(scrub_flags(v) for v in obj if not _is_flag_attribute(v))
    if isinstance(obj, str):
        return FLAG_PHRASE.sub(FLAG_REDACTED, obj)
    return obj


def _is_flag_attribute(item: object) -> bool:
    key = item.get("key") if isinstance(item, dict) else None
    return isinstance(key, str) and bool(FLAG_PATTERN.search(key))
