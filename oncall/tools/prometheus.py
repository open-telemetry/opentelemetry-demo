# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Prometheus Telemetry Tool for Live Microservice Golden Signals.
Queries live Prometheus (:9090) for:
- P95 Response Latency via span metrics & HTTP duration buckets
- HTTP 5xx / gRPC error rates per second
- Request throughput (RPS)
Enforces:
- Real live measurements first; missing telemetry is never treated as zero or healthy
- Captures evaluation timestamps and sliding window parameters
- Test fixtures only permitted when explicitly requested (allow_fixtures=True)
"""

import os
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from oncall.models import TelemetryObservation, TelemetryCitation

PROMETHEUS_HOST = os.environ.get("PROMETHEUS_HOST", "localhost")
PROMETHEUS_PORT = os.environ.get("PROMETHEUS_PORT", "9090")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", f"http://{PROMETHEUS_HOST}:{PROMETHEUS_PORT}")

DEFAULT_THRESHOLDS_MS = {
    "frontend": 1000.0,
    "checkout": 1000.0,
    "payment": 1000.0,
    "cart": 500.0,
    "shipping": 500.0,
    "ad": 500.0,
    "recommendation": 1000.0,
    "product-catalog": 1000.0,
    "email": 1000.0,
    "default": 1000.0
}


class PrometheusTool:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or PROMETHEUS_URL).rstrip("/")
        self.timeout = 2.5

    def check_connection(self) -> Dict[str, Any]:
        """Checks whether the live Prometheus instance is reachable and responding."""
        url = f"{self.base_url}/api/v1/query"
        try:
            resp = requests.get(url, params={"query": "up"}, timeout=self.timeout)
            if resp.status_code == 200 and resp.json().get("status") == "success":
                results = resp.json().get("data", {}).get("result", [])
                return {
                    "connected": True,
                    "status": "CONNECTED",
                    "monitored_targets": len(results),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            return {
                "connected": False,
                "status": "DEGRADED",
                "error": f"HTTP status {resp.status_code}",
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "connected": False,
                "status": "DISCONNECTED",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat()
            }

    def query(self, promql: str) -> Dict[str, Any]:
        """Execute an instant PromQL query against Prometheus."""
        url = f"{self.base_url}/api/v1/query"
        try:
            resp = requests.get(url, params={"query": promql}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "errorType": "connection_error", "error": str(e)}

    def inspect_service_metrics(self, service_name: str, allow_fixtures: bool = False) -> TelemetryObservation:
        """Inspect key Golden Signals (Latency P95, Error Rate, RPS) for a service."""
        eval_time = datetime.now(timezone.utc).isoformat()
        threshold_ms = DEFAULT_THRESHOLDS_MS.get(service_name, DEFAULT_THRESHOLDS_MS["default"])

        # 1. Try span metrics duration (milliseconds)
        span_latency_query = (
            f'histogram_quantile(0.95, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket'
            f'{{service_name="{service_name}"}}[5m])))'
        )
        latency_resp = self.query(span_latency_query)
        is_live = latency_resp.get("status") == "success" and bool(latency_resp.get("data", {}).get("result"))

        p95_val_ms: Optional[float] = None
        err_val_rps: float = 0.0
        rps_val: float = 0.0

        if is_live:
            try:
                raw_p95 = latency_resp["data"]["result"][0]["value"][1]
                if raw_p95 not in ("NaN", "+Inf", "-Inf"):
                    p95_val_ms = float(raw_p95)
            except Exception:
                p95_val_ms = None

        # 2. If span metrics not available, try standard HTTP server duration (seconds)
        if p95_val_ms is None:
            http_latency_query = (
                f'histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket'
                f'{{service_name="{service_name}"}}[5m])))'
            )
            http_resp = self.query(http_latency_query)
            if http_resp.get("status") == "success" and bool(http_resp.get("data", {}).get("result")):
                try:
                    raw_p95_sec = http_resp["data"]["result"][0]["value"][1]
                    if raw_p95_sec not in ("NaN", "+Inf", "-Inf"):
                        p95_val_ms = float(raw_p95_sec) * 1000.0
                        is_live = True
                except Exception:
                    pass

        # 3. Query Error Rate (combining span errors and HTTP 5xx)
        if is_live:
            err_query = (
                f'sum(rate(traces_span_metrics_duration_milliseconds_count'
                f'{{service_name="{service_name}", status_code="STATUS_CODE_ERROR"}}[5m])) or '
                f'sum(rate(http_server_request_duration_seconds_count'
                f'{{service_name="{service_name}", http_response_status_code=~"5.."}}[5m])) or vector(0)'
            )
            err_resp = self.query(err_query)
            if err_resp.get("status") == "success" and bool(err_resp.get("data", {}).get("result")):
                try:
                    err_val_rps = float(err_resp["data"]["result"][0]["value"][1])
                except Exception:
                    err_val_rps = 0.0

            # 4. Query Throughput
            throughput_query = (
                f'sum(rate(traces_span_metrics_duration_milliseconds_count'
                f'{{service_name="{service_name}"}}[5m])) or '
                f'sum(rate(http_server_request_duration_seconds_count'
                f'{{service_name="{service_name}"}}[5m])) or vector(0)'
            )
            thru_resp = self.query(throughput_query)
            if thru_resp.get("status") == "success" and bool(thru_resp.get("data", {}).get("result")):
                try:
                    rps_val = float(thru_resp["data"]["result"][0]["value"][1])
                except Exception:
                    rps_val = 0.0

        citations = []
        if is_live and p95_val_ms is not None:
            p95_sec = p95_val_ms / 1000.0
            summary = (
                f"Service '{service_name}' metrics at {eval_time[:19]}Z [Live Prometheus]: P95 Latency = {p95_val_ms:.1f}ms "
                f"(threshold: {threshold_ms:.0f}ms), Error Rate = {err_val_rps:.2f} req/s, Throughput = {rps_val:.1f} req/s (5m sliding window)."
            )
            data = {
                "p95_latency_sec": round(p95_sec, 3),
                "p95_latency_ms": round(p95_val_ms, 1),
                "error_rate_rps": round(err_val_rps, 3),
                "throughput_rps": round(rps_val, 1),
                "evaluation_time_utc": eval_time,
                "query_window": "5m sliding rate",
                "threshold_ms": threshold_ms,
                "live": True,
                "status": "CRITICAL" if (p95_val_ms > 2 * threshold_ms or err_val_rps > 5.0) else ("WARNING" if (p95_val_ms > threshold_ms or err_val_rps > 0.5) else "HEALTHY")
            }
            citations.append(
                TelemetryCitation(
                    source_type="prometheus_metric",
                    identifier=span_latency_query,
                    summary=f"P95 latency observed: {p95_val_ms:.1f}ms (window: 5m, eval_time: {eval_time[:19]}Z)",
                    evidence_payload={"p95_latency_ms": p95_val_ms, "promql": span_latency_query, "live": True}
                )
            )
            return TelemetryObservation(
                tool_name="prometheus_inspect_service",
                success=True,
                summary=summary,
                data=data,
                citations=citations
            )

        # Handle telemetry unavailable or offline
        if allow_fixtures:
            # Deterministic fixtures permitted strictly for offline test suites
            SERVICE_PROFILES = {
                "frontend": (5420.0, 0.0, 110.0, "Elevated P95 Latency detected = 5420ms (SLA threshold exceeded > 1000ms), downstream gateway bottleneck."),
                "cart": (2450.0, 14.2, 85.0, "Elevated P95 Latency detected = 2450ms (normal baseline < 50ms), Error Rate = 14.2 req/s (HTTP 500 spike)."),
                "checkout": (2510.0, 18.5, 42.0, "Elevated P95 Latency detected = 2510ms, Error Rate = 18.5 req/s (downstream timeout)."),
                "ad": (3100.0, 3.4, 120.0, "Elevated P95 Latency detected = 3100ms (GC pause delays, high CPU load)."),
                "payment": (2480.0, 22.0, 38.0, "Elevated P95 Latency detected = 2480ms, Error Rate = 22.0 req/s (gateway unreachable)."),
                "shipping": (23.0, 0.0, 85.0, "Service 'shipping' metrics: NORMAL HEALTH. P95 latency is 23.0ms (< 50ms threshold), zero error rate."),
            }
            if service_name in SERVICE_PROFILES:
                p95_ms, err_val_rps, rps_val, summary_desc = SERVICE_PROFILES[service_name]
            else:
                p95_ms, err_val_rps, rps_val = 35.0, 0.0, 100.0
                summary_desc = f"Service '{service_name}' metrics: NORMAL HEALTH (nominal baseline)."

            data = {
                "p95_latency_sec": p95_ms / 1000.0,
                "p95_latency_ms": p95_ms,
                "error_rate_rps": err_val_rps,
                "throughput_rps": rps_val,
                "evaluation_time_utc": eval_time,
                "query_window": "5m sliding rate (fixture)",
                "threshold_ms": threshold_ms,
                "live": False,
                "status": "CRITICAL" if (p95_ms > 2 * threshold_ms or err_val_rps > 5.0) else ("WARNING" if (p95_ms > threshold_ms or err_val_rps > 0.5) else "HEALTHY")
            }
            citations.append(
                TelemetryCitation(
                    source_type="prometheus_metric",
                    identifier=span_latency_query,
                    summary=f"P95 latency observed: {p95_ms:.1f}ms [Test Fixture]",
                    evidence_payload={"p95_latency_ms": p95_ms, "live": False}
                )
            )
            return TelemetryObservation(
                tool_name="prometheus_inspect_service",
                success=True,
                summary=summary_desc,
                data=data,
                citations=citations
            )

        # In production live mode: Missing telemetry is NEVER marked healthy or assumed zero!
        return TelemetryObservation(
            tool_name="prometheus_inspect_service",
            success=False,
            summary=f"Service '{service_name}' metrics unavailable from live Prometheus (:9090).",
            data={
                "p95_latency_sec": None,
                "p95_latency_ms": None,
                "error_rate_rps": None,
                "throughput_rps": None,
                "evaluation_time_utc": eval_time,
                "threshold_ms": threshold_ms,
                "live": False,
                "status": "UNKNOWN",
                "error": "Metrics unavailable or query returned no data"
            },
            citations=[]
        )
