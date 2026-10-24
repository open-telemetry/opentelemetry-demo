from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from oncall.contracts import Evidence, Incident

FAULT_CLASSES = ("app_error", "container_down", "cpu_throttle", "traffic_flood", "network_fault", "unknown")
ActionName = Literal["RESET_FEATURE_FLAG", "RESTART_CONTAINER", "THROTTLE_TRAFFIC", "ESCALATE_TO_HUMAN"]

ACTION_API_TYPE = {
    "RESET_FEATURE_FLAG": "toggle_flag",
    "RESTART_CONTAINER": "restart_service",
    "THROTTLE_TRAFFIC": "throttle_load",
}


class Diagnosis(BaseModel):
    """component/cause are the cross-team contract; root_cause_service/summary are kept in sync for the agent."""
    incident_id: str = ""
    component: str = "unknown"
    cause: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    escalate: bool = True
    root_cause_service: str = "unknown"
    fault_class: str = "unknown"
    summary: str = ""
    next_steps: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync(self) -> Diagnosis:
        if self.component == "unknown" and self.root_cause_service != "unknown":
            self.component = self.root_cause_service
        elif self.root_cause_service == "unknown" and self.component != "unknown":
            self.root_cause_service = self.component
        if not self.cause and self.summary:
            self.cause = self.summary
        elif not self.summary and self.cause:
            self.summary = self.cause
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class Plan(BaseModel):
    """Approved by a human before it reaches the action layer."""
    incident_id: str = ""
    action: ActionName
    target: str
    reason: str
    params: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class ActionResult(BaseModel):
    incident_id: str = ""
    action: ActionName
    target: str
    executed: bool
    dry_run: bool
    recovered: bool | None = None
    rolled_back: bool = False
    detail: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class IncidentRecord(BaseModel):
    """End-to-end envelope: Incident -> Evidence -> Diagnosis -> Plan -> ActionResult."""
    incident: Incident
    evidence: list[Evidence] = Field(default_factory=list)
    diagnosis: Diagnosis
    plan: Plan | None = None
    result: ActionResult | None = None


def to_submission(diagnosis: Diagnosis) -> dict[str, Any]:
    """Single mapping point to the organisers' JSON schema; identity until the schema is known."""
    return diagnosis.to_dict()
