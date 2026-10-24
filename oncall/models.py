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


class TelemetryCitation(BaseModel):
    """Specific observation evidence cited to justify a diagnostic conclusion."""
    source_type: Literal["prometheus_metric", "jaeger_trace", "opensearch_log", "flagd_config", "system_health"]
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
    target_service: str
    root_cause_service: str
    failure_mode: str
    confidence_score: float = Field(ge=0.0, le=1.0, description="Calibrated confidence between 0.0 and 1.0")
    
    # Evidence categorization required by hackathon criteria
    confirmed_facts: List[str] = Field(default_factory=list, description="Empirical facts directly observed from telemetry")
    likely_causes: List[str] = Field(default_factory=list, description="Causal inferences supported by correlated evidence")
    unresolved_hypotheses: List[str] = Field(default_factory=list, description="Hypotheses evaluated and ruled out or requiring further data")
    
    # Evidence consistency validation
    evidence_consistency_passed: bool = Field(default=True, description="Whether proposed action is consistent with current state")
    consistency_errors: List[str] = Field(default_factory=list, description="Reasons for consistency failure if any")
    
    investigation_steps: List[InvestigationStep] = Field(default_factory=list)
    citations: List[TelemetryCitation] = Field(default_factory=list)
    explanation: str
    recommended_action: str
    action_type: Literal["RESET_FEATURE_FLAG", "RESTART_CONTAINER", "THROTTLE_TRAFFIC", "ESCALATE_TO_HUMAN"]
    is_mitigated: bool = False
