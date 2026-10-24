from __future__ import annotations

from datetime import datetime, timedelta, timezone

from oncall.clients.backends import docker_containers, docker_events
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.guard import is_banned_service
from oncall.tools.registry import tool

LIFECYCLE = ("start", "stop", "die", "restart", "kill", "oom")


def _parse(stamp: str | None) -> datetime | None:
    if not stamp or stamp.startswith("0001-"):  # Docker's "never happened"
        return None
    return datetime.fromisoformat(stamp)  # 3.11+ accepts 'Z' and truncates nanoseconds



@tool(
    name="get_deploy_history",
    description=(
        "Container lifecycle in the last N minutes: which containers were started, stopped, restarted or died, "
        "with times, plus the restart count of containers that restarted. Shows what changed recently."
    ),
    params={"window_minutes": {"type": "integer", "description": "look-back window in minutes"}},
    required=["window_minutes"],
)
def get_deploy_history(window_minutes: int) -> ToolOutput:
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=window_minutes)
    seen: set[tuple[str, str, str]] = set()
    events = []

    def add(when: datetime, container: str, event: str) -> None:
        key = (when.strftime("%H:%M"), container, event)
        if since <= when <= now and not is_banned_service(container) and key not in seen:
            seen.add(key)
            events.append({"time": when.strftime("%H:%M:%S"), "container": container, "event": event})

    # 1) Docker's event stream. It is a short in-memory buffer that health-check exec events flood within
    #    minutes, so it is often empty.
    for event in docker_events(since, now, LIFECYCLE):
        add(datetime.fromtimestamp(event["time"], timezone.utc), event["Actor"]["Attributes"].get("name", ""),
            event["Action"])

    # 2) Each container's own last start/stop time: always available, survives the event buffer.
    infos = docker_containers()
    for info in infos:
        name, state = info["Name"].lstrip("/"), info.get("State", {})
        finished, started = _parse(state.get("FinishedAt")), _parse(state.get("StartedAt"))
        if finished:
            add(finished, name, "oom_killed" if state.get("OOMKilled") else "stopped")
        if started and (state.get("Status") == "running" or (finished and started > finished)):
            add(started, name, "started")

    events.sort(key=lambda e: e["time"])
    restarted = [
        {"container": i["Name"].lstrip("/"), "image": i["Config"]["Image"], "restarts": i["RestartCount"]}
        for i in infos
        if i["RestartCount"] and not is_banned_service(i["Name"].lstrip("/"))
    ]
    changed = sorted({e["container"] for e in events})
    summary = (f"{len(events)} container lifecycle changes in last {window_minutes}m "
               f"(containers: {changed or 'none'}); containers with restarts: {[r['container'] for r in restarted] or 'none'}")
    lines = [f"{e['time']} {e['container']} {e['event']}" for e in events[-30:]]
    return ToolOutput(text="\n".join([summary, *lines]), facts=[Fact(signal=Signal.DEPLOY, summary=summary, data={"events": events[-30:], "restarted": restarted})])
