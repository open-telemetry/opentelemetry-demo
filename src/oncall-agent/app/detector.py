from datetime import datetime, timezone
import json
import time
from typing import Any
import uuid

import httpx
from pydantic import BaseModel, Field

from app.config import (
    ACTION_API_URL,
    HOST_FALLBACK_URLS,
    PROMETHEUS_URL,
)


class Symptom(BaseModel):
    type: str
    service: str
    metric: str
    value: Any
    threshold: Any
    description: str


class Alert(BaseModel):
    incident_id: str
    timestamp: str
    fingerprint: str
    symptoms: list[Symptom]


class Detector:
    def __init__(self, min_requests: int = 5) -> None:
        self.min_requests = min_requests
        self._consecutive_error_polls: dict[str, int] = {}
        self._consecutive_cpu_polls: dict[str, int] = {}
        self._resolved_cooldowns: dict[str, float] = {}
        self._active_fingerprints: set[str] = set()

    def _query_prom(self, promql: str) -> list[dict[str, Any]]:
        urls = [PROMETHEUS_URL, HOST_FALLBACK_URLS.get("prometheus", "http://localhost:9090")]
        for url in urls:
            try:
                with httpx.Client(timeout=6.0) as client:
                    resp = client.get(f"{url}/api/v1/query", params={"query": promql})
                    if resp.status_code == 200:
                        return resp.json().get("data", {}).get("result", [])
            except Exception:
                pass
        return []

    def _query_containers(self) -> list[dict[str, Any]]:
        urls = [ACTION_API_URL, HOST_FALLBACK_URLS.get("action_api", "http://localhost:8201")]
        for url in urls:
            try:
                with httpx.Client(timeout=6.0) as client:
                    resp = client.get(f"{url}/containers")
                    if resp.status_code == 200:
                        return resp.json()
            except Exception:
                pass
        return []

    def evaluate_once(self, force_single_poll_trigger: bool = False) -> Alert | None:
        symptoms: list[Symptom] = []
        now = time.time()

        # 1. Evaluate container states via Action API inspector
        containers = self._query_containers()
        for c in containers:
            name = c.get("name", "unknown")
            # Skip infrastructure or non-app containers if needed, but inspector returns project containers
            if name in ("action-api", "oncall-agent"):
                continue

            state = c.get("state", "unknown")
            health = c.get("health", "none")
            restarts = c.get("restart_count", 0)
            oom = c.get("oom_killed", False)

            if state != "running":
                symptoms.append(
                    Symptom(
                        type="container_down",
                        service=name,
                        metric="container_state",
                        value=state,
                        threshold="running",
                        description=f"Container '{name}' is not running (state={state})",
                    )
                )

            if health == "unhealthy":
                symptoms.append(
                    Symptom(
                        type="container_unhealthy",
                        service=name,
                        metric="health_status",
                        value=health,
                        threshold="healthy",
                        description=f"Container '{name}' health check failed (status={health})",
                    )
                )

            if oom:
                symptoms.append(
                    Symptom(
                        type="container_oom",
                        service=name,
                        metric="oom_killed",
                        value=True,
                        threshold=False,
                        description=f"Container '{name}' was killed by OOM (Out Of Memory)",
                    )
                )

            if restarts >= 3:
                symptoms.append(
                    Symptom(
                        type="container_restarts",
                        service=name,
                        metric="restart_count",
                        value=restarts,
                        threshold=3,
                        description=f"Container '{name}' has restarted {restarts} times",
                    )
                )

        # 2. Evaluate span metrics: error ratio and latency p95
        calls_q = "sum by (service_name) (rate(traces_span_metrics_calls_total[2m]))"
        errors_q = 'sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[2m]))'
        p95_q = "histogram_quantile(0.95, sum by (service_name, le) (rate(traces_span_metrics_duration_milliseconds_bucket[2m])))"
        base_p95_q = "histogram_quantile(0.95, sum by (service_name, le) (rate(traces_span_metrics_duration_milliseconds_bucket[30m])))"

        calls_res = self._query_prom(calls_q)
        errors_res = self._query_prom(errors_q)
        p95_res = self._query_prom(p95_q)
        base_res = self._query_prom(base_p95_q)

        rps_map: dict[str, float] = {}
        for r in calls_res:
            svc = r.get("metric", {}).get("service_name")
            if svc:
                try:
                    rps_map[svc] = float(r.get("value", [0, 0])[1])
                except (ValueError, IndexError):
                    pass

        err_map: dict[str, float] = {}
        for r in errors_res:
            svc = r.get("metric", {}).get("service_name")
            if svc:
                try:
                    err_map[svc] = float(r.get("value", [0, 0])[1])
                except (ValueError, IndexError):
                    pass

        p95_map: dict[str, float] = {}
        for r in p95_res:
            svc = r.get("metric", {}).get("service_name")
            if svc:
                try:
                    val = float(r.get("value", [0, 0])[1])
                    if val == val:
                        p95_map[svc] = val
                except (ValueError, IndexError):
                    pass

        base_map: dict[str, float] = {}
        for r in base_res:
            svc = r.get("metric", {}).get("service_name")
            if svc:
                try:
                    val = float(r.get("value", [0, 0])[1])
                    if val == val:
                        base_map[svc] = val
                except (ValueError, IndexError):
                    pass

        for svc, rps in rps_map.items():
            err_rps = err_map.get(svc, 0.0)
            err_pct = (err_rps / rps * 100.0) if rps > 0 else 0.0

            # Error threshold: > 5% error ratio with >= N requests
            if err_pct > 5.0 and (rps * 300) >= self.min_requests:
                self._consecutive_error_polls[svc] = self._consecutive_error_polls.get(svc, 0) + 1
                if force_single_poll_trigger or self._consecutive_error_polls[svc] >= 2:
                    symptoms.append(
                        Symptom(
                            type="error_ratio",
                            service=svc,
                            metric="error_percentage",
                            value=round(err_pct, 2),
                            threshold=5.0,
                            description=f"Service '{svc}' error ratio is {err_pct:.1f}% (> 5% threshold, {self._consecutive_error_polls[svc]} polls)",
                        )
                    )
            else:
                self._consecutive_error_polls[svc] = 0

            # Latency threshold: p95 > max(1000ms, 2x baseline)
            p95 = p95_map.get(svc, 0.0)
            base = base_map.get(svc, p95)
            latency_thresh = max(1000.0, 2.0 * base)
            if p95 > latency_thresh and p95 > 1000.0:
                symptoms.append(
                    Symptom(
                        type="latency_p95",
                        service=svc,
                        metric="p95_duration_ms",
                        value=round(p95, 2),
                        threshold=round(latency_thresh, 2),
                        description=f"Service '{svc}' p95 latency is {p95:.1f}ms (> {latency_thresh:.1f}ms baseline)",
                    )
                )

        if not symptoms:
            return None

        # Build deduplication fingerprint
        fingerprint = ":".join(sorted(f"{s.service}:{s.type}" for s in symptoms))

        # Check cooldown
        last_resolved = self._resolved_cooldowns.get(fingerprint, 0.0)
        if (now - last_resolved) < 300.0:
            return None

        inc_suffix = uuid.uuid4().hex[:6].upper()
        ts_now = datetime.now(timezone.utc)
        incident_id = f"INC-{ts_now.strftime('%Y%m%d-%H%M%S')}-{inc_suffix}"

        return Alert(
            incident_id=incident_id,
            timestamp=ts_now.isoformat(),
            fingerprint=fingerprint,
            symptoms=symptoms,
        )

    def mark_resolved(self, fingerprint: str) -> None:
        self._resolved_cooldowns[fingerprint] = time.time()
        self._active_fingerprints.discard(fingerprint)


detector = Detector()
