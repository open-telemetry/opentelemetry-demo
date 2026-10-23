from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from app.config import ACTION_API_URL, HOST_FALLBACK_URLS

logger = logging.getLogger("oncall-agent.executor")

ONCALL_SETTLE_S = int(os.environ.get("ONCALL_SETTLE_S", 120))
ONCALL_DRY_RUN_DEFAULT = os.environ.get("ONCALL_DRY_RUN_DEFAULT", "true").lower() == "true"


def _api_url() -> str:
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{ACTION_API_URL}/health")
            if r.status_code == 200:
                return ACTION_API_URL
    except Exception:
        pass
    return HOST_FALLBACK_URLS.get("action_api", "http://localhost:8201")


def dry_run_action(
    incident_id: str,
    action: str,
    params: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    """Call Action API in dry_run=true mode and return its response."""
    url = _api_url()
    payload = {
        "action": action,
        "params": params,
        "incident_id": incident_id,
        "approval_token": token,
        "dry_run": True,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(f"{url}/actions", json=payload)
            return {"status_code": r.status_code, "body": r.json()}
    except Exception as e:
        return {"status_code": -1, "body": {"error": str(e)}}


def execute_action(
    incident_id: str,
    action: str,
    params: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    """Call Action API in live mode (dry_run=false) and return its response."""
    url = _api_url()
    payload = {
        "action": action,
        "params": params,
        "incident_id": incident_id,
        "approval_token": token,
        "dry_run": False,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{url}/actions", json=payload)
            return {"status_code": r.status_code, "body": r.json(), "action_id": r.json().get("action_id")}
    except Exception as e:
        return {"status_code": -1, "body": {"error": str(e)}, "action_id": None}


def rollback_action(incident_id: str, action_id: str, token: str) -> dict[str, Any]:
    """Call Action API rollback for a previously executed action_id."""
    url = _api_url()
    payload = {
        "action": "rollback",
        "params": {"action_id": action_id},
        "incident_id": incident_id,
        "approval_token": token,
        "dry_run": False,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(f"{url}/actions", json=payload)
            return {"status_code": r.status_code, "body": r.json()}
    except Exception as e:
        return {"status_code": -1, "body": {"error": str(e)}}


def verify_recovery(component: str, settle_s: int = ONCALL_SETTLE_S) -> dict[str, Any]:
    """Wait settle_s then verify the component has recovered via Prometheus and container health."""
    from app.config import PROMETHEUS_URL
    from app.tools.containers import get_container_health
    from app.tools.jaeger import search_traces

    logger.info("Waiting %ds for metrics to settle after action on %s...", settle_s, component)
    time.sleep(settle_s)

    result: dict[str, Any] = {
        "component": component,
        "settle_s": settle_s,
        "checks": {},
    }

    # Check 1: Prometheus error ratio
    try:
        urls = [PROMETHEUS_URL, HOST_FALLBACK_URLS.get("prometheus", "http://localhost:9090")]
        err_ratio: float | None = None
        for url in urls:
            try:
                import httpx as _httpx
                with _httpx.Client(timeout=6.0) as client:
                    q = f'sum(rate(traces_span_metrics_calls_total{{status_code="STATUS_CODE_ERROR",service_name="{component}"}}[2m])) / sum(rate(traces_span_metrics_calls_total{{service_name="{component}"}}[2m])) * 100'
                    r = client.get(f"{url}/api/v1/query", params={"query": q})
                    if r.status_code == 200:
                        res = r.json().get("data", {}).get("result", [])
                        if res:
                            err_ratio = float(res[0]["value"][1])
                        break
            except Exception:
                continue
        result["checks"]["error_ratio_pct"] = err_ratio
        result["checks"]["error_ratio_ok"] = err_ratio is not None and err_ratio < 2.0
    except Exception as e:
        result["checks"]["error_ratio_ok"] = False
        result["checks"]["error_ratio_err"] = str(e)

    # Check 2: Container health
    try:
        health_text = get_container_health(service=component)
        result["checks"]["container_health_raw"] = health_text[:300]
        result["checks"]["container_ok"] = (
            "State: running" in health_text
            and "Health: healthy" in health_text
        )
    except Exception as e:
        result["checks"]["container_ok"] = False
        result["checks"]["container_err"] = str(e)

    # Check 3: No new error traces in the last minute
    try:
        trace_text = search_traces(service=component, error_only=True, lookback_min=1, limit=3)
        has_recent_errors = "Trace" in trace_text and "[ERROR" in trace_text
        result["checks"]["no_new_errors_ok"] = not has_recent_errors
        result["checks"]["trace_check_raw"] = trace_text[:200]
    except Exception as e:
        result["checks"]["no_new_errors_ok"] = False
        result["checks"]["trace_err"] = str(e)

    passed = (
        result["checks"].get("error_ratio_ok", False)
        and result["checks"].get("container_ok", False)
        and result["checks"].get("no_new_errors_ok", False)
    )
    result["passed"] = passed
    return result
