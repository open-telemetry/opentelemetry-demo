"""Prometheus v3 client for querying RED metrics, latencies, and service health."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from .base import TelemetryClient
from .exceptions import TelemetryDataError, TelemetryResponseError
from ..models.evidence import MetricDataPoint


class PrometheusClient(TelemetryClient):
    """Client for Prometheus API in the OpenTelemetry Demo ecosystem."""

    def __init__(
        self,
        base_url: str = "http://localhost:9090",
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__(base_url=base_url, timeout_seconds=timeout_seconds, session=session)

    def health_check(self) -> bool:
        """Check if Prometheus is healthy."""
        try:
            resp = self.session.get(
                f"{self.base_url}/-/healthy",
                timeout=min(self.timeout_seconds, 3.0),
            )
            if resp.ok:
                return True
            # Fallback to simple query check
            data = self._request("GET", "/api/v1/query", params={"query": "up"})
            return data.get("status") == "success"
        except Exception:
            return False

    def query(self, promql: str, time: Optional[str] = None) -> Dict[str, Any]:
        """Execute an instant PromQL query."""
        params: Dict[str, Any] = {"query": promql}
        if time:
            params["time"] = time

        data = self._request("GET", "/api/v1/query", params=params)
        if data.get("status") != "success":
            err_msg = data.get("error", "Prometheus returned non-success status")
            err_type = data.get("errorType", "unknown")
            raise TelemetryResponseError(f"Prometheus error ({err_type}): {err_msg}")

        return data

    def query_range(
        self,
        promql: str,
        start: str | float,
        end: str | float,
        step: int = 15,
    ) -> Dict[str, Any]:
        """Execute a PromQL range query over a time interval."""
        params = {
            "query": promql,
            "start": str(start),
            "end": str(end),
            "step": f"{step}s",
        }
        data = self._request("GET", "/api/v1/query_range", params=params)
        if data.get("status") != "success":
            err_msg = data.get("error", "Prometheus returned non-success status")
            raise TelemetryResponseError(f"Prometheus range query error: {err_msg}")

        return data

    def query_scalar(self, promql: str) -> Optional[float]:
        """Execute an instant query and return the first scalar value, or None if empty."""
        data = self.query(promql)
        results = data.get("data", {}).get("result", [])
        if not results:
            return None
        try:
            # Value is [timestamp, "value_string"]
            val_str = results[0]["value"][1]
            return float(val_str)
        except (IndexError, KeyError, ValueError, TypeError) as e:
            raise TelemetryDataError(f"Failed to extract scalar from result: {results[0]}") from e

    # The demo's collector exports span metrics for every instrumented service,
    # which covers gRPC and Kafka services that emit no HTTP server metrics.
    SPAN_CALLS = "traces_span_metrics_calls_total"
    SPAN_DURATION_BUCKET = "traces_span_metrics_duration_milliseconds_bucket"
    INBOUND_KINDS = "SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"
    BASELINE_OFFSET = "30m"
    INFRA_SERVICES = frozenset({
        "agent", "chatbot", "mcp", "flagd", "flagd-ui", "telemetry-docs",
        "load-generator", "otel-collector", "jaeger", "opamp-server",
    })

    def _scalar_or_none(self, promql: str) -> Optional[float]:
        try:
            val = self.query_scalar(promql)
        except TelemetryDataError:
            return None
        if val is None or val != val:  # NaN from 0/0
            return None
        return val

    def get_service_metrics(
        self,
        service_name: str,
        lookback_seconds: int = 300,
    ) -> List[MetricDataPoint]:
        """RED + container metrics for a service, each with a baseline from 30 minutes earlier."""
        now_iso = datetime.now(timezone.utc).isoformat()
        window = f"{max(int(lookback_seconds), 60)}s"
        svc = f'service_name="{service_name}"'
        inbound = f'{svc}, span_kind=~"{self.INBOUND_KINDS}"'
        err = 'status_code="STATUS_CODE_ERROR"'

        def ratio(sel: str) -> str:
            total = f"sum(rate({self.SPAN_CALLS}{{{sel}}}[{window}]{{off}}))"
            return f"(sum(rate({self.SPAN_CALLS}{{{sel}, {err}}}[{window}]{{off}})) or {total} * 0) / {total}"

        queries = [
            ("error_rate_ratio", "ratio", ratio(inbound)),
            ("p95_latency_ms", "ms",
             f"histogram_quantile(0.95, sum by (le) (rate({self.SPAN_DURATION_BUCKET}{{{inbound}}}[{window}]{{off}})))"),
            ("requests_per_second", "req/s", f"sum(rate({self.SPAN_CALLS}{{{inbound}}}[{window}]{{off}}))"),
            ("outbound_error_rate_ratio", "ratio", ratio(f'{svc}, span_kind=~"SPAN_KIND_CLIENT|SPAN_KIND_PRODUCER"')),
            ("cpu_utilization_percent", "percent",
             f'avg(avg_over_time(container_cpu_utilization_ratio{{container_name="{service_name}"}}[{window}]{{off}}))'),
            ("memory_usage_bytes", "bytes",
             f'avg(avg_over_time(container_memory_usage_total_bytes{{container_name="{service_name}"}}[{window}]{{off}}))'),
        ]

        metrics: List[MetricDataPoint] = []
        for name, unit, template in queries:
            observed = self._scalar_or_none(template.replace("{off}", ""))
            if observed is None:
                continue
            baseline = self._scalar_or_none(template.replace("{off}", f" offset {self.BASELINE_OFFSET}"))
            metrics.append(
                MetricDataPoint(
                    metric_name=name,
                    service=service_name,
                    baseline_value=round(baseline, 4) if baseline is not None else None,
                    observed_value=round(observed, 4),
                    unit=unit,
                    timestamp=now_iso,
                )
            )
        return metrics

    def get_services_overview(
        self, lookback_seconds: int = 300, include_infra: bool = False
    ) -> Dict[str, Dict[str, float]]:
        """Per-service inbound error ratio, p95 latency and throughput, for triage."""
        window = f"{max(int(lookback_seconds), 60)}s"
        inbound = f'span_kind=~"{self.INBOUND_KINDS}"'
        total = f"sum by (service_name) (rate({self.SPAN_CALLS}{{{inbound}}}[{window}]))"
        queries = {
            "error_rate_ratio": (
                f'(sum by (service_name) (rate({self.SPAN_CALLS}{{{inbound}, status_code="STATUS_CODE_ERROR"}}[{window}])) '
                f"or {total} * 0) / {total}"
            ),
            "p95_latency_ms": (
                f"histogram_quantile(0.95, sum by (service_name, le) "
                f"(rate({self.SPAN_DURATION_BUCKET}{{{inbound}}}[{window}])))"
            ),
            "requests_per_second": f"sum by (service_name) (rate({self.SPAN_CALLS}{{{inbound}}}[{window}]))",
        }
        overview: Dict[str, Dict[str, float]] = {}
        for metric, promql in queries.items():
            for row in self.query(promql).get("data", {}).get("result", []):
                name = row.get("metric", {}).get("service_name")
                try:
                    val = float(row["value"][1])
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                if not name or (not include_infra and name in self.INFRA_SERVICES):
                    continue
                if val == val:
                    overview.setdefault(name, {})[metric] = round(val, 4)
        return overview
