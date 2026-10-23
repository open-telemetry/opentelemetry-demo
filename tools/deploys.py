"""deploy_history(): when each container of the demo's compose project last started, from Docker.

There is no deploy system here, so "a deploy" means a container (re)start or recreate.
Limitation: `make start --force-recreate` (or any full `docker compose up` after a change)
restarts everything at once, so every container looks recently deployed and the
"started later than the others" signal carries no information. The tool says so when
it sees that.
"""
import statistics
import subprocess
from datetime import datetime, timezone

from tools import sanitize
from tools.containers import PROJECT_LABEL, PROJECT_NAME, DockerProblem, _docker, parse_inspect
from tools.endpoints import compose_project
from tools.result import ToolResult, backend_error, iso, utc_now

TOOL = "deploy_history"
LIST_TIMEOUT = 10
INSPECT_TIMEOUT = 20
MAX_ITEMS = 12  # newest starts; the summary lists every recently restarted container
LATER_THAN_OTHERS_S = 300  # started this long after the typical container => "restarted recently"
NEVER_STARTED = "0001-01-01"  # what Docker reports for a container that was created but never run


def parse_time(text: str | None) -> datetime | None:
    """Docker timestamps carry nanoseconds ('2026-10-23T17:25:19.123456789Z'); keep microseconds."""
    if not text or text.startswith(NEVER_STARTED):
        return None
    whole, _, fraction = text.rstrip("Z").partition(".")
    try:
        return datetime.fromisoformat(f"{whole}.{(fraction + '000000')[:6]}").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def build_rows(inspected: list[dict], now: datetime) -> list[dict]:
    rows = []
    for c in inspected:
        started = parse_time(c["started_at"])
        rows.append({
            "name": c["name"],
            "status": c["status"],
            "started_at": iso(started) if started else None,
            "age_seconds": int((now - started).total_seconds()) if started else None,
            "restart_count": c["restart_count"],
        })
    ages = [r["age_seconds"] for r in rows if r["age_seconds"] is not None]
    typical = statistics.median(ages) if ages else None
    for r in rows:
        later = typical is not None and r["age_seconds"] is not None and typical - r["age_seconds"] > LATER_THAN_OTHERS_S
        r["restarted_recently"] = later or r["restart_count"] > 0
    # Newest start first: the most recent change is the first thing to look at.
    rows.sort(key=lambda r: (r["age_seconds"] is None, r["age_seconds"] or 0))
    return rows


def deploy_history(project: str | None = None, runner=subprocess.run) -> ToolResult:
    project = project or compose_project()
    now = utc_now()
    window = {"at": iso(now)}
    query = [f"docker ps -a -q --filter label={PROJECT_LABEL}={project}", "docker inspect <ids of the project's containers>"]

    if not PROJECT_NAME.match(project):
        return backend_error(TOOL, query, window, f"invalid compose project name {project!r}")
    try:
        ids = _docker(["ps", "-a", "-q", "--filter", f"label={PROJECT_LABEL}={project}"], LIST_TIMEOUT, runner).split()
        if not ids:
            return ToolResult(TOOL, "no_data", query, window, notes=[f"docker lists no containers for compose project {project!r}"])
        inspected = parse_inspect(_docker(["inspect", *ids], INSPECT_TIMEOUT, runner))
    except DockerProblem as exc:
        return backend_error(TOOL, query, window, str(exc))
    except (ValueError, AttributeError) as exc:
        return backend_error(TOOL, query, window, f"could not parse docker inspect output: {exc}")

    inspected, removed = sanitize.clean_counted(inspected)
    if not inspected:
        return ToolResult(TOOL, "no_data", query, window, notes=["no containers left after filtering", sanitize.removal_note(removed)])
    rows = build_rows(inspected, now)

    recent = [r["name"] for r in rows if r["restarted_recently"]]
    ages = [r["age_seconds"] for r in rows if r["age_seconds"] is not None]
    extra = {"summary": {
        "total": len(rows),
        "restarted_recently": recent,
        "median_age_seconds": int(statistics.median(ages)) if ages else None,
        "newest_start": rows[0]["started_at"],
    }}
    notes = [
        "a deploy here means a container start or recreate; `restarted_recently` = restart count above 0, "
        f"or started more than {LATER_THAN_OTHERS_S}s after the median container",
        "`make start --force-recreate` makes every container look recently started; then only restart_count and the spread of start times mean anything",
    ]
    if ages and max(ages) - min(ages) <= LATER_THAN_OTHERS_S:
        notes.append("all containers started within a few minutes of each other: this looks like a whole-stack start, so start times say nothing about one service")
    notes.append(sanitize.removal_note(removed))
    return ToolResult(TOOL, "data", query, window, items=rows[:MAX_ITEMS], total_items=len(rows), extra=extra, notes=notes)
