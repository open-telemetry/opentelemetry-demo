"""
models.py - Shared contracts for Diagnosis and Telemetry.
"""
from enum import Enum
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class ConfidenceLabel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ToolStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"

class TimeWindow(BaseModel):
    start_time: datetime
    end_time: datetime

class Evidence(BaseModel):
    evidence_id: str
    status: ToolStatus
    source: str
    service: str
    event_time_window: TimeWindow
    collection_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool: str
    query: str
    observed_value: Any
    trace_or_log_id: Optional[str] = None
    local_capture_reference: Optional[str] = None

class Incident(BaseModel):
    id: str
    source: str
    symptom: str
    affected_service: Optional[str] = None
    detection_time: datetime
    observation_window: TimeWindow
    recovery_condition: str

class Diagnosis(BaseModel):
    suspected_component: str
    suspected_cause: str
    supporting_evidence_ids: List[str]  # MUST match Neha's Evidence IDs
    conflicting_evidence_ids: List[str]
    alternatives: List[str]
    uncertainty: str
    confidence_label: ConfidenceLabel
    next_step: str
