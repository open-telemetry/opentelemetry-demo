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

    def get_service_metrics(
        self,
        service_name: str,
        lookback_seconds: int = 300,
    ) -> List[MetricDataPoint]:
        """Retrieve key RED and health metrics for a target service."""
        now_iso = datetime.now(timezone.utc).isoformat()
        metrics: List[MetricDataPoint] = []

        # 1. Error rate indicator (HTTP 5xx or gRPC non-zero status)
        error_rate_query = (
            f'sum(rate(http_server_duration_milliseconds_count{{http_response_status_code=~"5..", service_name=~".*{service_name}.*"}}[5m])) '
            f'/ sum(rate(http_server_duration_milliseconds_count{{service_name=~".*{service_name}.*"}}[5m]))'
        )
        try:
            err_val = self.query_scalar(error_rate_query)
            if err_val is not None:
                metrics.append(
                    MetricDataPoint(
                        metric_name="http_error_rate_ratio",
                        service=service_name,
                        baseline_value=0.0,
                        observed_value=round(err_val, 4),
                        unit="ratio",
                        timestamp=now_iso,
                    )
                )
        except TelemetryDataError:
            pass

        # 2. Latency (p95 request duration in milliseconds)
        latency_p95_query = (
            f'histogram_quantile(0.95, sum(rate(http_server_duration_milliseconds_bucket{{service_name=~".*{service_name}.*"}}[5m])) by (le))'
        )
        try:
            latency_val = self.query_scalar(latency_p95_query)
            if latency_val is not None and latency_val > 0:
                metrics.append(
                    MetricDataPoint(
                        metric_name="p95_request_latency",
                        service=service_name,
                        baseline_value=50.0,
                        observed_value=round(latency_val, 2),
                        unit="ms",
                        timestamp=now_iso,
                    )
                )
        except TelemetryDataError:
            pass

        # 3. Request count rate (throughput)
        throughput_query = (
            f'sum(rate(http_server_duration_milliseconds_count{{service_name=~".*{service_name}.*"}}[5m]))'
        )
        try:
            tp_val = self.query_scalar(throughput_query)
            if tp_val is not None:
                metrics.append(
                    MetricDataPoint(
                        metric_name="requests_per_second",
                        service=service_name,
                        baseline_value=10.0,
                        observed_value=round(tp_val, 2),
                        unit="req/s",
                        timestamp=now_iso,
                    )
                )
        except TelemetryDataError:
            pass

        return metrics
