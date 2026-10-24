"""General fault categories and the telemetry signals that indicate them.

These are reasoning aids for the LLM, not answers: no category is tied to a
specific service.
"""

from typing import get_args

from oncall.models import Category

CLIENT_SERVICES = ("load-generator", "frontend-web")

CATEGORIES: dict[str, str] = {
    "app_error": (
        "ERROR spans originating in one service (the deepest error span), "
        "error_type/error_message present, error logs in that service; "
        "its container is healthy"
    ),
    "dependency_unavailable": (
        "connection refused/timeout errors to a backing store or downstream "
        "service; that dependency's container is down/unhealthy or it is "
        "absent from traces"
    ),
    "container_down": (
        "container not running, restarting or OOMKilled; its callers show "
        "connection errors"
    ),
    "resource_cpu": (
        "latency up, CPU high in container_health, GC logs/metrics up; "
        "error rate may be about normal"
    ),
    "resource_memory": (
        "memory % rising toward the limit, restarts/OOM, latency degrading over time"
    ),
    "network_degradation": (
        "latency/timeouts between two specific services, both containers "
        "healthy, no application exceptions"
    ),
    "traffic_surge": (
        "requests per second sharply up at the entry point (frontend/proxy), "
        "latency up broadly, few application exceptions"
    ),
    "upstream_propagation": (
        "a service shows errors only because a downstream service it calls is "
        "failing; never the final answer, follow it down"
    ),
    "unknown": "evidence is insufficient or contradictory",
    "no_incident": (
        "no regression anywhere: error rates and p95 latency at or below their "
        "baselines, all containers running; only known background noise "
        "(clients, collector export errors). Decision no_action"
    ),
}

assert set(CATEGORIES) == set(get_args(Category)), "taxonomy out of sync with models"


def render() -> str:
    """The taxonomy as prompt text, one category per line."""
    return "\n".join(f"- {name}: {signals}" for name, signals in CATEGORIES.items())
