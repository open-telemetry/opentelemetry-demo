"""Evidence collector aggregating traces, metrics, and logs for a target service."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..config import Settings
from ..models.evidence import EvidenceBundle, MetricDataPoint
from ..telemetry.jaeger_client import JaegerClient
from ..telemetry.opensearch_client import OpenSearchClient
from ..telemetry.prometheus_client import PrometheusClient

# Derived from upstream OpenTelemetry Demo dependency topology
DEFAULT_SERVICE_EDGES: Dict[str, List[str]] = {
    "frontend": ["ad", "recommendation", "product-catalog", "cart", "checkout"],
    "checkout": ["cart", "payment", "shipping", "email", "product-catalog", "currency"],
    "recommendation": ["product-catalog"],
    "shipping": ["quote"],
    "cart": ["valkey-cart"],
    "accounting": ["postgresql", "kafka"],
    "fraud-detection": ["kafka"],
    "ad": [],
    "currency": [],
    "email": [],
    "payment": [],
    "product-catalog": [],
    "quote": [],
}


class EvidenceCollector:
    """Collects and normalizes multi-signal telemetry evidence into an EvidenceBundle.
    
    Robust against partial backend outages: failures in any individual telemetry store
    are tracked explicitly in metadata rather than silently ignored.
    """

    def __init__(
        self,
        jaeger_client: Optional[JaegerClient] = None,
        prometheus_client: Optional[PrometheusClient] = None,
        opensearch_client: Optional[OpenSearchClient] = None,
        settings: Optional[Settings] = None,
        service_topology: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        cfg = settings or Settings()
        self.jaeger_client = jaeger_client or JaegerClient(base_url=cfg.jaeger_url)
        self.prometheus_client = prometheus_client or PrometheusClient(base_url=cfg.prometheus_url)
        self.opensearch_client = opensearch_client or OpenSearchClient(base_url=cfg.opensearch_url)
        self.topology = service_topology or DEFAULT_SERVICE_EDGES

    def collect_evidence(
        self,
        service_name: str,
        lookback_seconds: int = 300,
    ) -> EvidenceBundle:
        """Collect traces, metrics, and logs for a specified service and time window.
        
        Explicitly distinguishes between:
        - Successful query finding 0 anomalies (valid healthy state)
        - Telemetry backend unavailability (error state tracked in metadata)
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        trace_ids: List[str] = []
        metrics: List[MetricDataPoint] = []
        log_excerpts: List[str] = []

        source_status: Dict[str, str] = {}
        source_errors: Dict[str, Optional[str]] = {}
        timing_ms: Dict[str, float] = {}

        # 1. Collect Jaeger traces
        if self.jaeger_client:
            t0 = time.perf_counter()
            try:
                trace_ids = self.jaeger_client.get_error_trace_ids(
                    service_name=service_name,
                    lookback_seconds=lookback_seconds,
                )
                source_status["jaeger"] = "available"
                source_errors["jaeger"] = None
            except Exception as e:
                source_status["jaeger"] = "unavailable"
                source_errors["jaeger"] = f"{type(e).__name__}: {str(e)}"
                trace_ids = []
            finally:
                timing_ms["jaeger"] = round((time.perf_counter() - t0) * 1000, 2)
        else:
            source_status["jaeger"] = "disabled"
            source_errors["jaeger"] = None

        # 2. Collect Prometheus metrics
        if self.prometheus_client:
            t0 = time.perf_counter()
            try:
                metrics = self.prometheus_client.get_service_metrics(
                    service_name=service_name,
                    lookback_seconds=lookback_seconds,
                )
                source_status["prometheus"] = "available"
                source_errors["prometheus"] = None
            except Exception as e:
                source_status["prometheus"] = "unavailable"
                source_errors["prometheus"] = f"{type(e).__name__}: {str(e)}"
                metrics = []
            finally:
                timing_ms["prometheus"] = round((time.perf_counter() - t0) * 1000, 2)
        else:
            source_status["prometheus"] = "disabled"
            source_errors["prometheus"] = None

        # 3. Collect OpenSearch logs
        if self.opensearch_client:
            t0 = time.perf_counter()
            try:
                log_excerpts = self.opensearch_client.get_error_logs(
                    service_name=service_name,
                    lookback_seconds=lookback_seconds,
                )
                source_status["opensearch"] = "available"
                source_errors["opensearch"] = None
            except Exception as e:
                source_status["opensearch"] = "unavailable"
                source_errors["opensearch"] = f"{type(e).__name__}: {str(e)}"
                log_excerpts = []
            finally:
                timing_ms["opensearch"] = round((time.perf_counter() - t0) * 1000, 2)
        else:
            source_status["opensearch"] = "disabled"
            source_errors["opensearch"] = None

        # Calculate service dependency graph (upstream callers and downstream dependencies)
        downstream = self.topology.get(service_name, [])
        upstream = [
            parent
            for parent, children in self.topology.items()
            if service_name in children
        ]
        dep_graph: Dict[str, List[str]] = {
            "upstream": upstream,
            "downstream": downstream,
        }

        metadata: Dict[str, Any] = {
            "source_status": source_status,
            "source_errors": source_errors,
            "backend_timing_ms": timing_ms,
            "lookback_seconds": lookback_seconds,
            "all_sources_available": all(v == "available" for v in source_status.values()),
            "partial_failure": any(v == "unavailable" for v in source_status.values()),
        }

        return EvidenceBundle(
            service_name=service_name,
            detection_timestamp=now_iso,
            trace_ids=trace_ids,
            metrics=metrics,
            log_excerpts=log_excerpts,
            dependency_graph=dep_graph,
            metadata=metadata,
        )
