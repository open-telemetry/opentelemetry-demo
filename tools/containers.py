"""container_health(): the state of every container in the demo's compose project.

This comes from the Docker engine, not Prometheus, because a stopped container emits no
metrics at all. All docker calls are fixed argument lists, no shell, with short timeouts.
"""
import json
import re
import subprocess

from tools import sanitize
from tools.endpoints import compose_project
from tools.result import ToolResult, backend_error, iso, utc_now

TOOL = "container_health"
PROJECT_LABEL = "com.docker.compose.project"
SERVICE_LABEL = "com.docker.compose.service"
LIST_TIMEOUT = 10
INSPECT_TIMEOUT = 20
STATS_TIMEOUT = 8
MAX_ITEMS = 60
PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")  # same rule compose uses for project names
GOOD_HEALTH = {"healthy", "none"}  # "none" = the image defines no health check


class DockerProblem(Exception):
    pass


def _docker(args: list[str], timeout: int, runner) -> str:
    try:
        result = runner(["docker", *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise DockerProblem(f"docker {args[0]} timed out after {timeout}s") from exc
    except OSError as exc:
        raise DockerProblem(f"cannot run docker: {exc}") from exc
    if result.returncode != 0:
        raise DockerProblem(f"docker {args[0]} failed: {result.stderr.strip()[:200]}")
    return result.stdout


def parse_inspect(raw_json: str) -> list[dict]:
    """Turn `docker inspect` output (a JSON array) into one flat dict per container."""
    rows = []
    for c in json.loads(raw_json):
        state = c.get("State", {})
        rows.append({
            "name": c.get("Name", "").lstrip("/"),
            "compose_service": c.get("Config", {}).get("Labels", {}).get(SERVICE_LABEL),
            "status": state.get("Status"),  # running, exited, restarting, paused, dead, created
            "health": state.get("Health", {}).get("Status", "none"),
            "restart_count": c.get("RestartCount", 0),
            "exit_code": state.get("ExitCode"),
            "oom_killed": bool(state.get("OOMKilled", False)),
            "started_at": state.get("StartedAt"),
            "finished_at": state.get("FinishedAt"),
        })
    return rows


def _needs_attention(row: dict) -> bool:
    return (
        row["status"] != "running"
        or row["health"] not in GOOD_HEALTH
        or row["restart_count"] > 0
        or row["oom_killed"]
    )


def _percent(text: str | None) -> float | None:
    try:
        return float(str(text).rstrip("%"))
    except ValueError:
        return None


def _add_stats(rows: list[dict], runner) -> str | None:
    """Add cpu_percent / memory_percent to running containers. Returns a note if it failed."""
    running = [r["name"] for r in rows if r["status"] == "running"]
    if not running:
        return None
    try:
        out = _docker(
            ["stats", "--no-stream", "--format", "{{json .}}", *running], STATS_TIMEOUT, runner
        )
        stats = {}
        for line in out.splitlines():
            if line.strip():
                entry = json.loads(line)
                stats[entry["Name"]] = entry
    except (DockerProblem, ValueError, KeyError) as exc:
        return f"cpu/memory unavailable (docker stats): {exc}"
    for row in rows:
        entry = stats.get(row["name"])
        if entry:
            row["cpu_percent"] = _percent(entry.get("CPUPerc"))
            row["memory_percent"] = _percent(entry.get("MemPerc"))
    return None


def container_health(include_stats: bool = True, project: str | None = None, runner=subprocess.run) -> ToolResult:
    project = project or compose_project()
    now = utc_now()
    window = {"at": iso(now)}
    list_cmd = f"docker ps -a -q --filter label={PROJECT_LABEL}={project}"
    inspect_cmd = "docker inspect <ids of the project's containers>"
    query = [list_cmd, inspect_cmd]
    if include_stats:
        query.append("docker stats --no-stream --format '{{json .}}' <running containers>")

    if not PROJECT_NAME.match(project):
        return backend_error(TOOL, query, window, f"invalid compose project name {project!r}")
    try:
        ids = _docker(
            ["ps", "-a", "-q", "--filter", f"label={PROJECT_LABEL}={project}"], LIST_TIMEOUT, runner
        ).split()
        if not ids:
            return ToolResult(
                TOOL, "no_data", query, window,
                notes=[f"docker lists no containers for compose project {project!r}"],
            )
        rows = parse_inspect(_docker(["inspect", *ids], INSPECT_TIMEOUT, runner))
    except DockerProblem as exc:
        return backend_error(TOOL, query, window, str(exc))
    except (ValueError, AttributeError) as exc:
        return backend_error(TOOL, query, window, f"could not parse docker inspect output: {exc}")

    # Drop the flag service's containers before anything else is counted or capped.
    rows = sanitize.clean(rows)
    notes = []
    if include_stats:
        note = _add_stats(rows, runner)
        if note:
            notes.append(note)

    # Containers that need a look come first, then the rest alphabetically.
    rows.sort(key=lambda r: (not _needs_attention(r), r["name"]))
    summary = {
        "total": len(rows),
        "running": sum(r["status"] == "running" for r in rows),
        "not_running": [r["name"] for r in rows if r["status"] != "running"],
        "unhealthy": [r["name"] for r in rows if r["status"] == "running" and r["health"] not in GOOD_HEALTH],
        "restarted": [r["name"] for r in rows if r["restart_count"] > 0],
        "oom_killed": [r["name"] for r in rows if r["oom_killed"]],
    }
    if not rows:
        return ToolResult(TOOL, "no_data", query, window, notes=["no containers left after filtering"])
    return ToolResult(
        TOOL, "data", query, window,
        items=rows[:MAX_ITEMS], total_items=len(rows), extra={"summary": summary}, notes=notes,
    )
