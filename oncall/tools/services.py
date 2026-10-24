from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from oncall.clients.backends import docker_containers, jaeger_services, opensearch_search, prom_query
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.guard import is_banned_service
from oncall.tools.registry import tool


def _compose_service(info: dict) -> str | None:
    return (info.get("Config", {}).get("Labels") or {}).get("com.docker.compose.service")


def container_states(infos: list[dict]) -> dict[str, str]:
    """Compose service name -> container state (running, exited, paused...)."""
    states = {_compose_service(i): i.get("State", {}).get("Status", "unknown") for i in infos}
    return {name: state for name, state in states.items() if name and not is_banned_service(name)}


def cpu_limits(infos: list[dict]) -> dict[str, float]:
    """Compose service name -> CPU limit in cores, only for containers that have one."""
    limits = {_compose_service(i): (i.get("HostConfig", {}).get("NanoCpus") or 0) / 1e9 for i in infos}
    return {name: cores for name, cores in limits.items() if name and cores > 0}


def _log_services() -> set[str]:
    body = {
        "size": 0,
        "query": {"range": {"@timestamp": {"gte": "now-15m"}}},
        "aggs": {"s": {"terms": {"field": "resource.service.name.keyword", "size": 100}}},
    }
    return {b["key"] for b in opensearch_search(body)["aggregations"]["s"]["buckets"]}


@tool(
    name="list_services",
    description=(
        "List every service seen in traces, span metrics and logs over the last 15 minutes, plus its docker "
        "container state. A service whose container is not running is DOWN; a container with a CPU limit set is CPU_LIMITED (possible throttling); a running container that "
        "emits no traces/metrics/logs is NO_TELEMETRY (normal for infrastructure such as databases or collectors). Start here to see what exists and what is missing."
    ),
    params={},
)
def list_services() -> ToolOutput:
    with ThreadPoolExecutor(max_workers=4) as pool:
        docker_job = pool.submit(docker_containers)  # one Docker listing feeds both states and CPU limits
        traces = pool.submit(jaeger_services)
        metrics = pool.submit(prom_query, "count by (service_name)(traces_span_metrics_calls_total)")
        logs = pool.submit(_log_services)
        infos = docker_job.result()
        containers, limits = container_states(infos), cpu_limits(infos)
        in_traces, in_logs = set(traces.result()), logs.result()
        in_metrics = {r["metric"]["service_name"] for r in metrics.result()}
    rows = []
    for name in sorted(in_traces | in_metrics | in_logs | set(containers)):
        if is_banned_service(name):
            continue
        state = containers.get(name, "n/a")
        telemetry = [n for n, seen in (("traces", in_traces), ("metrics", in_metrics), ("logs", in_logs)) if name in seen]
        if state not in ("running", "n/a"):
            status = "DOWN"
        elif name in limits:
            status = "CPU_LIMITED"
        elif state == "running" and not telemetry:
            status = "NO_TELEMETRY"
        else:
            status = "ok"
        rows.append({"service": name, "container": state, "telemetry": telemetry, "status": status, "cpu_limit_cores": limits.get(name, 0)})
    problems = [r["service"] for r in sorted(rows, key=lambda r: r["status"] == "NO_TELEMETRY") if r["status"] != "ok"]
    summary = f"{len(rows)} services; not ok: {problems or 'none'}"
    lines = [f"{r['service']}: container={r['container']} status={r['status']} seen_in={r['telemetry']} cpu_limit={r['cpu_limit_cores'] or 'none'}" for r in sorted(rows, key=lambda r: r["status"] == "NO_TELEMETRY") if r["status"] != "ok"]
    healthy = ", ".join(r["service"] for r in rows if r["status"] == "ok")
    return ToolOutput(text="\n".join([summary, *lines, f"ok: {healthy}"]), facts=[Fact(signal=Signal.CONTAINER, summary=summary, data={"services": rows})])
