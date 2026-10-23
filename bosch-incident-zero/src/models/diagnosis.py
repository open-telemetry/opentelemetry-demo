"""Structured data models for root-cause diagnosis results."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .incident import IncidentReport, IncidentSeverity, IncidentStatus, EvidencePayload, RemediationPayload


class DiagnosisStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    SUSPECTED = "SUSPECTED"
    DEGRADED_PERFORMANCE = "DEGRADED_PERFORMANCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_ANOMALY_DETECTED = "NO_ANOMALY_DETECTED"


class FailureMode(str, Enum):
    DEPENDENCY_OUTAGE = "DEPENDENCY_OUTAGE"
    INTERNAL_SERVICE_ERROR = "INTERNAL_SERVICE_ERROR"
    RESOURCE_STARVATION_CPU = "RESOURCE_STARVATION_CPU"
    MEMORY_LEAK = "MEMORY_LEAK"
    LATENCY_DEGRADATION = "LATENCY_DEGRADATION"
    CASCADING_SYMPTOMATIC_FAILURE = "CASCADING_SYMPTOMATIC_FAILURE"
    TELEMETRY_OUTAGE = "TELEMETRY_OUTAGE"
    UNKNOWN = "UNKNOWN"


class RootCauseCandidate(BaseModel):
    """Represents a potential root cause evaluated by diagnostic rules."""
    service: str = Field(..., description="Service identified as the root cause origin")
    failure_mode: FailureMode = Field(..., description="Classified failure category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    rank: int = Field(..., ge=1, description="Rank ordered by evidence strength (1 = primary)")
    reasoning: str = Field(..., description="Explainable rationale for this candidate and its rank")
    supporting_signals: List[str] = Field(default_factory=list, description="Citations of signals that support this cause")
    is_dependency: bool = Field(default=False, description="True if this is a dependency rather than the investigated service")
    severity: IncidentSeverity = Field(default=IncidentSeverity.HIGH)


class DiagnosisResult(BaseModel):
    """Comprehensive, explainable diagnostic output from the Root Cause Analyzer."""
    investigated_service: str
    diagnosis_timestamp: str
    status: DiagnosisStatus
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    primary_root_cause: Optional[RootCauseCandidate] = None
    candidates: List[RootCauseCandidate] = Field(default_factory=list)
    supporting_evidence: Dict[str, Any] = Field(default_factory=dict)
    contradictory_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    scoring_breakdown: Dict[str, Any] = Field(default_factory=dict)
    recommended_next_step: str

    def to_incident_report(
        self,
        incident_id: str,
        recommended_action: str = "Investigate root cause and apply remediation",
        action_parameters: Optional[Dict[str, Any]] = None,
        dry_run: bool = True,
    ) -> IncidentReport:
        """Convert diagnosis result into a schema-compliant IncidentReport."""
        target_svc = self.primary_root_cause.service if self.primary_root_cause else self.investigated_service
        impacted: List[str] = []
        if target_svc != self.investigated_service:
            impacted.append(self.investigated_service)

        sev = self.primary_root_cause.severity if self.primary_root_cause else IncidentSeverity.MEDIUM

        # Extract trace IDs from supporting evidence
        trace_ids = self.supporting_evidence.get("trace_ids") or []
        if not trace_ids:
            raise ValueError(
                f"No trace evidence for {self.investigated_service}; the incident schema requires "
                "at least one real trace ID, so escalate instead of reporting."
            )

        metrics_sum = self.supporting_evidence.get("metrics_summary") or {}
        logs_sum = self.supporting_evidence.get("log_excerpts") or []

        inc_status = IncidentStatus.DIAGNOSED if self.primary_root_cause else IncidentStatus.DETECTED

        summary = (
            self.primary_root_cause.reasoning
            if self.primary_root_cause
            else f"Investigation of {self.investigated_service}: status {self.status.value}"
        )

        action_id = f"ACT-{incident_id}"
        return IncidentReport(
            incident_id=incident_id,
            timestamp=self.diagnosis_timestamp,
            status=inc_status,
            target_service=target_svc,
            impacted_services=impacted,
            severity=sev,
            root_cause_summary=summary,
            confidence_score=self.overall_confidence,
            evidence=EvidencePayload(
                trace_ids=trace_ids,
                metrics_summary=metrics_sum,
                log_excerpts=logs_sum,
            ),
            remediation=RemediationPayload(
                action_id=action_id,
                recommended_action=recommended_action,
                action_parameters=action_parameters or {},
                requires_approval=True,
                approval_status="PENDING",
                dry_run=dry_run,
            ),
        )
