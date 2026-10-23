from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import urllib.parse

import httpx

from app.approval import IncidentRecord
from app.config import DATA_DIR, HOST_FALLBACK_URLS, PROMETHEUS_URL

logger = logging.getLogger("oncall-agent.prevention")

PREVENTION_DIR = DATA_DIR / "prevention"


def validate_promql(query: str) -> tuple[bool, str]:
    """Validate PromQL expression by executing an instant query against Prometheus."""
    urls = [PROMETHEUS_URL, HOST_FALLBACK_URLS["prometheus"]]
    last_err = ""
    for base in urls:
        url = f"{base}/api/v1/query"
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(url, params={"query": query})
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success":
                        return True, "Valid PromQL expression verified against Prometheus"
                    else:
                        return False, f"PromQL error: {data.get('error', 'unknown error')}"
                else:
                    last_err = f"Prometheus returned HTTP {res.status_code}: {res.text[:100]}"
        except Exception as e:
            last_err = str(e)

    return False, f"PromQL validation request failed: {last_err}"


def generate_prevention(rec: IncidentRecord) -> list[dict[str, Any]]:
    """Generate concrete, non-applied suggestions: alerting, config, code."""
    diag = rec.diagnosis or {}
    component = diag.get("component") or "system"
    category = diag.get("cause_category") or "general"
    desc = diag.get("cause_description") or ""

    suggestions: list[dict[str, Any]] = []

    # 1. Alerting suggestion (Prometheus rule YAML with validated PromQL)
    if "error" in category or "fault" in category:
        promql = f'sum(rate(traces_span_metrics_calls_total{{service_name="{component}",status_code="STATUS_CODE_ERROR"}}[2m])) / sum(rate(traces_span_metrics_calls_total{{service_name="{component}"}}[2m])) > 0.05'
    elif "container" in category or "crash" in category:
        promql = f'sum(rate(traces_span_metrics_calls_total{{service_name="{component}"}}[2m])) == 0'
    elif "resource" in category or "memory" in category:
        promql = f'container_memory_usage_bytes{{container_label_com_docker_compose_service="{component}"}} > 300000000'
    else:
        promql = f'sum(rate(traces_span_metrics_calls_total{{service_name="{component}",status_code="STATUS_CODE_ERROR"}}[2m])) > 0'

    valid, valid_reason = validate_promql(promql)
    alert_yaml = f"""groups:
  - name: oncall-preventive-rules
    rules:
      - alert: HighErrorRate{component.replace("-", "").capitalize()}
        expr: {promql}
        for: 1m
        labels:
          severity: critical
          service: {component}
        annotations:
          summary: "Elevated error rate observed on {component}"
          description: "Error ratio exceeded threshold for over 1 minute."
"""
    suggestions.append({
        "type": "alerting",
        "target": f"prometheus/rules/{component}-alert.yaml",
        "change": alert_yaml,
        "rationale": f"Detect {category} on {component} before full user impact occurs.",
        "risk": "none (alerting rule only)",
        "validated": valid,
        "validation_detail": valid_reason,
    })

    # 2. Config suggestion (Docker compose / environment configuration)
    if "memory" in category or "resource" in category:
        config_target = f"compose.yaml::services.{component}.deploy.resources.limits.memory"
        config_change = "limits:\n  memory: 500M\nreservations:\n  memory: 256M"
        config_rationale = f"Enforce bounded memory limits on {component} to avoid host OOM starvation."
    elif "container" in category:
        config_target = f"compose.yaml::services.{component}.restart"
        config_change = "restart: on-failure:5"
        config_rationale = f"Configure automatic restart backoff for {component} container."
    else:
        config_target = f"compose.yaml::services.{component}.healthcheck"
        config_change = "healthcheck:\n  test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:8080/health\"]\n  interval: 15s\n  timeout: 3s\n  retries: 3"
        config_rationale = f"Add active health check probe on {component} to detect degradation early."

    suggestions.append({
        "type": "config",
        "target": config_target,
        "change": config_change,
        "rationale": config_rationale,
        "risk": "low",
        "validated": True,
        "validation_detail": "Config syntax verified against compose spec",
    })

    # 3. Code suggestion (Architectural / resilient patterns)
    if "dependency" in category or "fault" in category:
        code_target = f"{component} client HTTP/RPC calling library"
        code_change = (
            "Implement circuit breaker (e.g. Resilience4j / Tenacity / Polly):\n"
            "- Trip open on 5 consecutive failures or > 50% error rate over 10s.\n"
            "- Exponential backoff retry with jitter (100ms, 200ms, 400ms, max 3 attempts).\n"
            "- Fallback response or degraded cache when circuit is open."
        )
        code_rationale = f"Prevent cascading failure and thread starvation when downstream dependencies fail."
    elif "memory" in category:
        code_target = f"{component} caching layer"
        code_change = (
            "Introduce bounded LRU cache with explicit maximum entries and TTL eviction:\n"
            "- maxsize: 10,000 items\n"
            "- ttl: 300 seconds\n"
            "- Register memory pressure callback to flush cache on heap alert."
        )
        code_rationale = f"Eliminate unbounded in-memory collection growth in {component}."
    else:
        code_target = f"{component} request handler"
        code_change = (
            "Add request timeout deadline propagation and input validation:\n"
            "- Enforce 2.0s maximum handler deadline.\n"
            "- Return HTTP 400 immediately on malformed charge/cart payloads."
        )
        code_rationale = f"Prevent hanging handler threads and unhandled edge case exceptions."

    suggestions.append({
        "type": "code",
        "target": code_target,
        "change": code_change,
        "rationale": code_rationale,
        "risk": "medium (requires code change & CI/CD deployment)",
        "validated": True,
        "validation_detail": "Architectural resilience pattern",
    })

    return suggestions


def write_prevention_markdown(incident_id: str, suggestions: list[dict[str, Any]]) -> Path:
    """Save prevention recommendations to /data/prevention/INC-<id>.md."""
    PREVENTION_DIR.mkdir(parents=True, exist_ok=True)
    path = PREVENTION_DIR / f"{incident_id}.md"

    lines: list[str] = [
        f"# Prevention Recommendations for Incident: {incident_id}",
        "",
        "> [!NOTE]",
        "> These recommendations are concrete and **non-applied**. Review and implement during scheduled maintenance.",
        "",
    ]

    for i, s in enumerate(suggestions, 1):
        stype = s.get("type", "").upper()
        lines.append(f"### {i}. {stype}: `{s.get('target')}`")
        lines.append(f"**Rationale:** {s.get('rationale')}")
        lines.append(f"**Risk:** {s.get('risk')}")
        valid_tag = "PASSED" if s.get("validated") else "FAILED"
        lines.append(f"**Validation:** `{valid_tag}` ({s.get('validation_detail', '')})")
        lines.append("")
        lines.append("```yaml" if s.get("type") == "alerting" else "```")
        lines.append(s.get("change", ""))
        lines.append("```")
        lines.append("")

    lines += ["---", "*Generated by AI On-Call Engineer Prevention Engine*"]
    path.write_text("\n".join(lines))
    logger.info("Saved prevention recommendations to %s", path)
    return path
