"""Data models for gathered incident evidence."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MetricDataPoint(BaseModel):
    """Represents a metric anomaly measurement."""
    metric_name: str
    service: str
    baseline_value: Optional[float] = None  # None = no baseline data available
    observed_value: float
    unit: str = ""
    timestamp: str


class EvidenceBundle(BaseModel):
    """Aggregated evidence across metrics, traces, and logs."""
    service_name: str
    detection_timestamp: str
    trace_ids: List[str] = Field(default_factory=list, description="List of failing trace IDs")
    metrics: List[MetricDataPoint] = Field(default_factory=list, description="Anomalous metrics")
    log_excerpts: List[str] = Field(default_factory=list, description="Correlated error logs")
    dependency_graph: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Upstream and downstream dependencies of the affected service"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
