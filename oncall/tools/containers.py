from __future__ import annotations

from typing import Any

from oncall.clients.backends import docker_inspect, prom_query
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.guard import is_banned_service
from oncall.tools.registry import tool


def inspect(name: str) -> dict[str, Any]:
    if is_banned_service(name):
        raise ValueError(f"service not available: {name}")
    return docker_inspect(name)


def cpu_cores_used(name: str) -> float | None:
    rows = prom_query(f'sum(rate(container_cpu_usage_nanoseconds_total{{container_name="{name}"}}[2m]))')
    return round(float(rows[0]["value"][1]) / 1e9, 3) if rows else None


@tool(
    name="get_container_stats",
    description=(
        "Docker state of one service's container: running/exited, exit code, restart count, CPU limit in cores "
        "(0 = unlimited), recent CPU cores used (Prometheus) and how saturated that is against the limit. "
        "Use it when a service is missing from traces, or when latency is high without errors."
    ),
    params={"service": {"type": "string", "description": "container/service name, e.g. payment"}},
    required=["service"],
)
def get_container_stats(service: str) -> ToolOutput:
    info = inspect(service)
    state = info["State"]
    limit = info["HostConfig"]["NanoCpus"] / 1e9
    used = cpu_cores_used(service)
    stats = {
        "service": service,
        "status": state["Status"],
        "exit_code": state["ExitCode"],
        "oom_killed": state["OOMKilled"],
        "restart_count": info["RestartCount"],
        "cpu_limit_cores": limit,
        "cpu_cores_used_2m": used,
        "cpu_saturation": round(used / limit, 2) if limit and used is not None else None,
    }
    summary = f"{service}: {stats['status']} exit={stats['exit_code']} restarts={stats['restart_count']} cpu_limit={limit or 'none'} cpu_used={used}"
    if stats["cpu_saturation"] is not None and stats["cpu_saturation"] > 0.8:
        summary += f" (saturated {stats['cpu_saturation']:.0%} of limit)"
    return ToolOutput(text=summary, facts=[Fact(signal=Signal.CONTAINER, summary=summary, data=stats)])
