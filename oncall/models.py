# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Data contracts and schema definitions for the AI On-Call Engineer.
Provides structured models for Alerts, Telemetry Observations, Citations,
Evidence Consistency Checks, and Evidence-Based Diagnoses.
"""

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field


class IncidentAlert(BaseModel):
    """Input alert received by the on-call agent."""
    alert_id: str
    service_name: str
    title: str
    severity: Literal["critical", "warning", "info"] = "warning"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str
    metric_name: Optional[str] = None
    threshold: Optional[str] = None
    annotations: Dict[str, str] = Field(default_factory=dict)
    
    # Snapshot fields for temporal consistency
    scenario_id: Optional[str] = None
    snapshot_p95_ms: Optional[float] = None
    snapshot_error_rate_rps: Optional[float] = None
    snapshot_timestamp_utc: Optional[str] = None


class TelemetryCitation(BaseModel):
    """Specific observation evidence cited to justify a diagnostic conclusion."""
    source_type: Literal["prometheus_metric", "jaeger_trace", "opensearch_log", "flagd_config", "system_health", "repository_context"]
    identifier: str = Field(description="Trace ID, Metric query, Log timestamp, or Flag key")
    summary: str
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)


class TelemetryObservation(BaseModel):
    """Observation returned by a telemetry inspection tool."""
    tool_name: str
    success: bool
    summary: str
    data: Dict[str, Any]
    citations: List[TelemetryCitation] = Field(default_factory=list)


class InvestigationStep(BaseModel):
    """Single step in the agent's iterative reasoning loop."""
    step_number: int
    intent: str
    tool_name: str
    tool_parameters: Dict[str, Any]
    observation: TelemetryObservation


class RootCauseDiagnosis(BaseModel):
    """Final evidence-based diagnosis produced by the on-call agent."""
    incident_id: str
    scenario_id: Optional[str] = None
    target_service: str
    root_cause_service: str
    is_downstream: bool = False
    failure_mode: str
    confidence_score: float = Field(ge=0.0, le=1.0, description="Calibrated confidence between 0.0 and 1.0")
    
    # Evidence categorization required by hackathon criteria
    confirmed_facts: List[str] = Field(default_factory=list, description="Empirical facts directly observed from telemetry")
    likely_causes: List[str] = Field(default_factory=list, description="Causal inferences supported by correlated evidence")
    unresolved_hypotheses: List[str] = Field(default_factory=list, description="Hypotheses evaluated and ruled out or requiring further data")
    
    # Temporal & telemetry state reconciliation
    incident_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Triggering alert measurements")
    current_telemetry: Dict[str, Any] = Field(default_factory=dict, description="Current live evaluation measurements")
    telemetry_reconciliation_status: Literal["ACTIVE_OUTAGE", "RECOVERED_SINCE_TRIGGER", "CONFLICTING_MEASUREMENTS", "NOMINAL_BASELINE"] = "ACTIVE_OUTAGE"
    
    # Detailed causal trace proof
    trace_summary: Dict[str, Any] = Field(default_factory=dict, description="Structured parent-child trace execution proof")
    
    # Log evidence status
    log_evidence_status: Literal["CORROBORATING_LOGS_FOUND", "NO_DATA", "UNAVAILABLE"] = "NO_DATA"
    
    # Deployment vs Repository context
    deployment_evidence_type: Literal["REPOSITORY_COMMIT_CONTEXT_ONLY", "VERIFIED_RUNTIME_DEPLOYMENT"] = "REPOSITORY_COMMIT_CONTEXT_ONLY"
    
    # Evidence consistency validation
    evidence_consistency_passed: bool = Field(default=True, description="Whether proposed action is consistent with current state")
    consistency_errors: List[str] = Field(default_factory=list, description="Reasons for consistency failure if any")
    
    investigation_steps: List[InvestigationStep] = Field(default_factory=list)
    citations: List[TelemetryCitation] = Field(default_factory=list)
    explanation: str
    recommended_action: str
    action_type: Literal["RESET_FEATURE_FLAG", "RESTART_CONTAINER", "THROTTLE_LOAD_GENERATOR", "SCALE_SERVICE", "ESCALATE_TO_HUMAN", "NO_ACTION"]
    action_status: Literal["PENDING_APPROVAL", "EXECUTED", "REJECTED", "NOT_REQUIRED"] = "PENDING_APPROVAL"
    verification_status: Literal["NOT_STARTED", "RECOVERED", "NOT_RECOVERED", "INCONCLUSIVE"] = "NOT_STARTED"
    is_mitigated: bool = False


class IncidentRecord(BaseModel):
    """
    Unified Single Source of Truth for a Live Operational Incident.
    Derives from real-time monitoring and diagnosis, keeping snapshot separate from live state.
    """
    incident_id: str
    alerted_service: str
    title: str
    severity: Literal["critical", "warning", "info"] = "warning"
    detection_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    current_status: Literal[
        "INVESTIGATING",
        "AWAITING_APPROVAL",
        "APPROVED",
        "REJECTED",
        "EXECUTING",
        "EXECUTION_FAILED",
        "VERIFYING_RECOVERY",
        "RECOVERED",
        "RECOVERY_UNCONFIRMED",
        "ESCALATED",
        "NO_ACTION_REQUIRED",
        "CLOSED"
    ] = "INVESTIGATING"
    root_cause_status: Literal["INVESTIGATING", "LIKELY", "CONFIRMED", "INCONCLUSIVE"] = "INVESTIGATING"
    
    # Triggering snapshot vs current live
    triggering_metric: str = "P95 Latency"
    threshold_ms: float = 1000.0
    triggering_measurement: Dict[str, Any] = Field(default_factory=dict)
    latest_live_measurement: Dict[str, Any] = Field(default_factory=dict)
    telemetry_evaluation_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    telemetry_reconciliation_status: Literal["ACTIVE_OUTAGE", "RECOVERED_SINCE_TRIGGER", "CONFLICTING_MEASUREMENTS", "NOMINAL_BASELINE"] = "ACTIVE_OUTAGE"
    
    # Root cause & causal proof
    root_cause_service: str = ""
    is_downstream: bool = False
    failure_mode: str = ""
    confidence_score: float = 0.0
    trace_ids: List[str] = Field(default_factory=list)
    span_ids: List[str] = Field(default_factory=list)
    trace_summary: Dict[str, Any] = Field(default_factory=dict)
    
    # Evidence categorization
    log_evidence_status: Literal["CORROBORATING_LOGS_FOUND", "NO_DATA", "UNAVAILABLE"] = "NO_DATA"
    correlated_logs: List[Dict[str, Any]] = Field(default_factory=list)
    deployment_evidence_type: Literal["REPOSITORY_COMMIT_CONTEXT_ONLY", "VERIFIED_RUNTIME_DEPLOYMENT"] = "REPOSITORY_COMMIT_CONTEXT_ONLY"
    confirmed_facts: List[str] = Field(default_factory=list)
    likely_causes: List[str] = Field(default_factory=list)
    unresolved_hypotheses: List[str] = Field(default_factory=list)
    citations: List[TelemetryCitation] = Field(default_factory=list)
    
    # Reviewer audit
    reviewer_verdict: Optional[Dict[str, Any]] = None
    
    # Safety gate & proposed remediation
    proposed_remediation: Optional[Dict[str, Any]] = None
    approval_status: Literal["NOT_REQUESTED", "AWAITING_APPROVAL", "APPROVED", "REJECTED", "SUPERSEDED", "NOT_REQUIRED"] = "NOT_REQUESTED"
    approval_token: Optional[str] = None
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None
    
    # Execution & verification
    execution_status: Literal["NOT_STARTED", "EXECUTING", "EXECUTED", "EXECUTION_FAILED", "SKIPPED"] = "NOT_STARTED"
    execution_result: Optional[Dict[str, Any]] = None
    execution_timestamp: Optional[str] = None
    recovery_verification_status: Literal["NOT_STARTED", "VERIFYING", "RECOVERED", "RECOVERY_UNCONFIRMED", "INCIDENT_PERSISTS", "FAILED"] = "NOT_STARTED"
    recovery_details: Optional[Dict[str, Any]] = None
    
    # Post-mortem report (ONLY generated when action is executed!)
    post_mortem_report: Optional[str] = None
    report_generated_at: Optional[str] = None
