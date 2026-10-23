from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

FAULT_CLASSES = ("app_error", "container_down", "cpu_throttle", "unknown")


class Diagnosis(BaseModel):
    root_cause_service: str = "unknown"
    fault_class: str = "unknown"
    confidence: float = 0.0
    summary: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    escalate: bool = True
    next_steps: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def to_submission(diagnosis: Diagnosis) -> dict[str, Any]:
    """Single mapping point to the organisers' JSON schema; identity until the schema is known."""
    return diagnosis.to_dict()
