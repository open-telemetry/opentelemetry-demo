from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Signal(str, Enum):
    TRACE = "trace"; METRIC = "metric"; LOG = "log"
    CONTAINER = "container"; DEPLOY = "deploy"; TRIAGE = "triage"


class Fact(BaseModel):
    """What a tool EMITS. The registry turns each Fact into an Evidence with an ID."""
    signal: Signal
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


class ToolOutput(BaseModel):
    ok: bool = True
    text: str
    facts: list[Fact] = Field(default_factory=list)
    error: str | None = None


class Evidence(BaseModel):
    id: str
    signal: Signal
    tool: str
    query: str
    ts: str
    summary: str
    data: dict[str, Any]


class Alert(BaseModel):
    alert_id: str
    fired_at: str
    kind: Literal["error_rate", "latency", "container", "traffic", "memory", "manual"]
    service: str | None = None
    value: float | None = None
    threshold: float | None = None
    description: str


class Incident(BaseModel):
    id: str
    symptom: str
    started_at: str
    window: str
    source: str


class ServiceSymptom(BaseModel):
    service: str
    error_rate: float
    baseline_error_rate: float
    p95_ms: float
    baseline_p95_ms: float
    rps: float
    baseline_rps: float
    origin_share: float = 0.0
    container_flags: list[str] = []
    suspicion: float = 0.0
    role: Literal["origin", "propagated_symptom", "unaffected", "unknown"] = "unknown"
    reasons: list[str] = []


class Hypothesis(BaseModel):
    id: str
    component: str
    fault_class: Literal["app_fault", "infra_fault", "overload", "dependency", "resource_exhaustion", "unknown"]
    statement: str
    prior: float
    confirm_with: list[str] = []
    falsify_with: list[str] = []


class SymptomDigest(BaseModel):
    window_minutes: int
    ranked: list[ServiceSymptom]
    hypotheses: list[Hypothesis]
    sample_error_trace_ids: list[str] = []
    notes: list[str] = []
