"""Shared contract types passed between tools, the agent brain and the safety module."""

from typing import Literal, TypedDict

MAX_SUMMARY_CHARS = 1500
MAX_EVIDENCE_ITEMS = 20


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
    decision: Literal["act", "escalate"]
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
