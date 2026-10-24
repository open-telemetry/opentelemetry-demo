"""container_health tool: read-only health of the demo's Docker containers.

Docker is only ever asked to *describe* containers: `docker ps`,
`docker inspect` and `docker stats`. Nothing here starts, stops, restarts or
changes a container (hackathon hard rule; a test scans this file to prove it).
"""

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from oncall.agent.taxonomy import CLIENT_SERVICES
from oncall.config import Settings, load_settings
from oncall.models import Evidence, ToolResult, make_error, make_result
from oncall.safety.exclusions import is_excluded
from oncall.tools.registry import register_tool

TOOL = "container_health"

# A container is flagged when it crosses any of these. Memory % is reported but
# never flagged: on the live demo checkout runs at ~98% of its 20 MiB limit while
# healthy, so only an actual OOM kill counts. CPU is flagged only for containers
# that have a CPU limit (none do by default), because going over one core is
# normal for a container without a limit, not starvation.
CPU_PCT_MAX = 90.0  # % of the container's CPU limit
RECENT_RESTART_MIN = 15  # restarted by Docker within this many minutes
BUSIEST_IN_SUMMARY = 3  # healthy containers with the most CPU/memory use
# Healthy containers kept as evidence (the busiest); the rest are only counted,
# which keeps the result small for the LLM's context.
HEALTHY_EVIDENCE = 5

DOCKER_TIMEOUT_S = 15
READ_ONLY_COMMANDS = ("ps", "inspect", "stats")

# Offline fixtures follow the same layout as the F03 telemetry backends:
# <OFFLINE_DIR or oncall/tests/fixtures>/<OFFLINE_SCENARIO or baseline>/
FIXTURE_FILE = "container_health.json"
DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


class DockerError(RuntimeError):
    """A docker command failed, timed out, or Docker is not running."""


def _subcommand(args: list[str]) -> str | None:
    """The docker subcommand in `args`, skipping `compose -f <file>` pairs."""
    i = 0
    if args[:1] == ["compose"]:
        i = 1
        while args[i : i + 1] == ["-f"]:
            i += 2
    return args[i] if i < len(args) else None


def _run_docker(args: list[str]) -> str:
    """Run a read-only docker command and return its stdout.

    The subcommand must be in READ_ONLY_COMMANDS; anything else is refused
    before it reaches Docker.
    """
    if _subcommand(args) not in READ_ONLY_COMMANDS:
        raise DockerError(f"refusing non read-only docker command: {args}")
    cmd = ["docker", *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=DOCKER_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DockerError(f"`{' '.join(cmd)}` failed: {exc}") from exc
    if proc.returncode != 0:
        raise DockerError(
            f"`{' '.join(cmd)}` exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        )
    return proc.stdout


def compose_container_ids(project: str) -> list[str]:
    """IDs of every container in this compose project, running or not."""
    label = f"label=com.docker.compose.project={project}"
    return _run_docker(["ps", "--all", "--quiet", "--filter", label]).split()


def inspect_containers(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    return json.loads(_run_docker(["inspect", *ids]))


def _stats(ids: list[str]) -> list[dict]:
    """One `docker stats` snapshot per container (running containers only)."""
    if not ids:
        return []
    out = _run_docker(["stats", "--no-stream", "--format", "{{json .}}", *ids])
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def load_fixture(settings: Settings) -> dict | None:
    base = Path(settings.OFFLINE_DIR or DEFAULT_FIXTURE_DIR)
    path = base / os.environ.get("OFFLINE_SCENARIO", "baseline") / FIXTURE_FILE
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _percent(value: object) -> float | None:
    """Turn docker stats text such as "12.5%" into 12.5; None if missing."""
    try:
        return float(str(value).rstrip("%"))
    except ValueError:
        return None


def _cpu_limit_cores(host_config: dict) -> float | None:
    """CPU limit in cores (e.g. 0.5), or None when the container has no limit."""
    nano = host_config.get("NanoCpus") or 0
    if nano > 0:
        return nano / 1e9
    quota = host_config.get("CpuQuota") or 0
    period = host_config.get("CpuPeriod") or 0
    if quota > 0 and period > 0:
        return quota / period
    return None


def parse_docker_time(value: str | None) -> datetime | None:
    """Parse Docker's "2026-10-23T09:12:01.123456789Z" to the second, in UTC."""
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _describe(info: dict, stats: dict | None) -> dict:
    """Pick the fields we care about out of one `docker inspect` entry."""
    state = info.get("State") or {}
    labels = (info.get("Config") or {}).get("Labels") or {}
    cpu_pct = mem_pct = None
    cpu_limit = _cpu_limit_cores(info.get("HostConfig") or {})
    if stats:
        cpu_pct = _percent(stats.get("CPUPerc"))
        if cpu_pct is not None and cpu_limit:
            cpu_pct = cpu_pct / cpu_limit
        mem_pct = _percent(stats.get("MemPerc"))
    return {
        "name": (info.get("Name") or "").lstrip("/"),
        "service": labels.get("com.docker.compose.service"),
        "state": state.get("Status"),
        "health": (state.get("Health") or {}).get("Status"),
        "restart_count": info.get("RestartCount") or 0,
        "oom_killed": bool(state.get("OOMKilled")),
        "exit_code": state.get("ExitCode"),
        "started_at": state.get("StartedAt"),
        "cpu_pct": cpu_pct,  # % of the CPU limit, or of one core if there is none
        "cpu_limited": cpu_limit is not None,
        "mem_pct": mem_pct,
    }


def _is_client(c: dict) -> bool:
    return (c["service"] or c["name"]) in CLIENT_SERVICES


def _problems(c: dict, now: datetime) -> list[str]:
    """Reasons this container looks unhealthy; empty list means healthy.

    Clients (the load generator) are never unhealthy: their state and usage are
    reported, but they are a traffic source, not a root-cause candidate.
    """
    if _is_client(c):
        return []
    problems = []
    if c["state"] != "running":
        problems.append(f"not running (state={c['state']}, exit_code={c['exit_code']})")
    if c["health"] == "unhealthy":
        problems.append("healthcheck unhealthy")
    if c["oom_killed"]:
        problems.append("OOM-killed")
    started = parse_docker_time(c["started_at"])
    if c["restart_count"] > 0 and started:
        minutes_ago = (now - started) / timedelta(minutes=1)
        if minutes_ago < RECENT_RESTART_MIN:
            problems.append(
                f"restarted {c['restart_count']} times, last start "
                f"{minutes_ago:.0f} min ago"
            )
    if c["cpu_limited"] and c["cpu_pct"] is not None and c["cpu_pct"] > CPU_PCT_MAX:
        problems.append(f"CPU {c['cpu_pct']:.0f}% of limit")
    return problems


def _fmt_pct(value: float | None, of: str) -> str:
    return "n/a" if value is None else f"{value:.1f}% of {of}"


def _busy(c: dict) -> float:
    """How loaded a container is: its higher CPU or memory %, 0 if unknown."""
    return max(c["cpu_pct"] or 0.0, c["mem_pct"] or 0.0)


def _usage(c: dict) -> str:
    cpu_of = "limit" if c["cpu_limited"] else "one core"
    return (
        f"cpu={_fmt_pct(c['cpu_pct'], cpu_of)}, mem={_fmt_pct(c['mem_pct'], 'limit')}"
    )


def _evidence_text(c: dict, problems: list[str]) -> str:
    if not problems:
        text = (
            f"{c['name']}: state={c['state']}, health={c['health'] or 'none'}, "
            f"{_usage(c)}"
        )
        if _is_client(c):
            text += " | client (traffic generator), never marked unhealthy"
        return text
    text = (
        f"{c['name']}: state={c['state']}, health={c['health'] or 'none'}, "
        f"restarts={c['restart_count']}, exit_code={c['exit_code']}, "
        f"oom_killed={str(c['oom_killed']).lower()}, started_at={c['started_at']}, "
        f"{_usage(c)}"
    )
    return text + " | FLAGGED: " + "; ".join(problems)


def check_containers(
    infos: list[dict],
    stats: list[dict],
    service: str | None,
    now: datetime,
    max_healthy: int | None = HEALTHY_EVIDENCE,
) -> ToolResult:
    """Turn raw `docker inspect` + `docker stats` output into a ToolResult.

    Evidence holds every flagged container and the `max_healthy` busiest healthy
    ones (all of them when None).
    """
    query = {"service": service}
    stats_by_name = {s.get("Name"): s for s in stats}
    if is_excluded(service):
        return make_error(TOOL, query, "service is not available to inspect")
    containers = []
    for info in infos:
        name = (info.get("Name") or "").lstrip("/")
        c = _describe(info, stats_by_name.get(name))
        if not (is_excluded(c["service"]) or is_excluded(c["name"])):
            containers.append(c)

    if service:
        known = sorted({c["service"] or c["name"] for c in containers})
        containers = [c for c in containers if service in (c["service"], c["name"])]
        if not containers:
            return make_error(
                TOOL,
                query,
                f"no container for service {service!r}. Known services: "
                + ", ".join(known),
            )

    if not containers:
        return make_result(
            TOOL,
            query,
            "No demo containers found. The demo may not be running.",
            [],
        )

    rows = [(c, _problems(c, now)) for c in containers]
    # Flagged first, then the busiest, so CPU/memory pressure survives the
    # 20-item evidence cap even though it is not flagged.
    rows.sort(key=lambda row: (not row[1], -_busy(row[0]), row[0]["name"]))
    flagged = [(c, p) for c, p in rows if p]
    if flagged:
        summary = f"{len(flagged)} of {len(rows)} containers unhealthy: " + "; ".join(
            f"{c['name']} ({', '.join(p)})" for c, p in flagged
        )
    else:
        summary = f"All {len(rows)} containers healthy."
    busiest = [c for c, p in rows if not p and _busy(c) > 0][:BUSIEST_IN_SUMMARY]
    if busiest:
        usage = "; ".join(
            f"{c['name']}{' (client)' if _is_client(c) else ''} {_usage(c)}"
            for c in busiest
        )
        summary = f"{summary.rstrip('.')}. Busiest: {usage}."

    ts = now.isoformat(timespec="seconds")
    healthy = [(c, p) for c, p in rows if not p]
    kept = flagged + (healthy if max_healthy is None else healthy[:max_healthy])
    if len(kept) < len(rows):
        summary = f"{summary.rstrip('.')}. Evidence lists {len(kept)} of {len(rows)}."
    evidence: list[Evidence] = [
        {"id": f"container:{c['name']}", "text": _evidence_text(c, p), "ts": ts}
        for c, p in kept
    ]
    return make_result(TOOL, query, summary, evidence)


@register_tool(
    TOOL,
    "Docker container state, restarts, OOM kills, CPU and memory. Spots "
    "stopped, crash-looping, OOM-killed or CPU-limited containers.",
    {
        "properties": {
            "service": {
                "type": "string",
                "description": "Omit to check all containers.",
            }
        }
    },
)
def container_health(service: str | None = None) -> ToolResult:
    """Report container health for one service, or all demo containers."""
    settings = load_settings()
    query = {"service": service}
    try:
        if settings.TELEMETRY_BACKEND == "offline":
            fixture = load_fixture(settings)
            if fixture is None:
                return make_error(TOOL, query, "container_health not available offline")
            now = parse_docker_time(fixture.get("captured_at")) or datetime.now(UTC)
            return check_containers(
                fixture.get("inspect", []), fixture.get("stats", []), service, now
            )

        infos = inspect_containers(compose_container_ids(settings.COMPOSE_PROJECT_NAME))
        running = [
            i["Id"] for i in infos if (i.get("State") or {}).get("Status") == "running"
        ]
        return check_containers(infos, _stats(running), service, datetime.now(UTC))
    except DockerError as exc:
        return make_error(TOOL, query, f"Docker not reachable: {exc}")
