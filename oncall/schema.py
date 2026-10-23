from __future__ import annotations

from pydantic import BaseModel, Field


class Diagnosis(BaseModel):
    incident_id: str = ""
    status: str = "uncertain_escalate"
    root_cause_component: str | None = None
    root_cause: str = ""
    fault_class: str = "unknown"
    confidence: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    affected_services: list[str] = Field(default_factory=list)
    reasoning_steps: list[str] = Field(default_factory=list)
