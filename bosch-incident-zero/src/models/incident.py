"""Structured incident report model matching config/incident_schema.json."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    DIAGNOSED = "DIAGNOSED"
    REMEDIATION_PENDING = "REMEDIATION_PENDING"
    REMEDIATED = "REMEDIATED"
    RESOLVED = "RESOLVED"
    ABORTED = "ABORTED"


class IncidentSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidencePayload(BaseModel):
    trace_ids: List[str] = Field(..., min_length=1)
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)
    log_excerpts: List[str] = Field(default_factory=list)


class RemediationPayload(BaseModel):
    action_id: Optional[str] = None
    recommended_action: str
    action_parameters: Dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = True
    approval_status: Optional[str] = "PENDING"
    dry_run: bool = True
    executed_at: Optional[str] = None
    recovery_verified: bool = False


class IncidentReport(BaseModel):
    """Schema-compliant incident report model."""
    incident_id: str
    timestamp: str
    status: IncidentStatus
    target_service: str
    impacted_services: List[str] = Field(default_factory=list)
    severity: IncidentSeverity
    root_cause_summary: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    evidence: EvidencePayload
    remediation: RemediationPayload

    def to_schema_dict(self) -> Dict[str, Any]:
        """Export as dictionary matching config/incident_schema.json."""
        return self.model_dump(mode="json")
