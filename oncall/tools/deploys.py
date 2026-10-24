from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from oncall.clients.backends import docker
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.guard import is_banned_service
from oncall.tools.registry import tool

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


@tool(
    name="get_deploy_history",
    description=(
        "Container lifecycle in the last N minutes: start/stop/restart/die events with times, plus the "
        "restart count of containers that restarted. Shows what was stopped, restarted or redeployed recently."
    ),
    params={"window_minutes": {"type": "integer", "description": "look-back window in minutes"}},
    required=["window_minutes"],
)
def get_deploy_history(window_minutes: int) -> ToolOutput:
    now = datetime.now(timezone.utc)
    raw = docker(
        "events", "--since", (now - timedelta(minutes=window_minutes)).strftime(TIME_FORMAT), "--until", now.strftime(TIME_FORMAT),
        "--filter", "type=container", "--filter", "event=start", "--filter", "event=stop", "--filter", "event=die",
        "--filter", "event=restart", "--filter", "event=kill", "--format", "{{json .}}",
    )
    events = []
    for line in raw.splitlines():
        event = json.loads(line)
        name = event["Actor"]["Attributes"].get("name", "")
        if not is_banned_service(name):
            when = datetime.fromtimestamp(event["time"], timezone.utc).strftime("%H:%M:%S")
            events.append({"time": when, "container": name, "event": event["Action"]})
    ids = docker("ps", "-aq").split()
    infos = json.loads(docker("inspect", *ids)) if ids else []
    restarted = [
        {"container": i["Name"].lstrip("/"), "image": i["Config"]["Image"], "restarts": i["RestartCount"]}
        for i in infos
        if i["RestartCount"] and not is_banned_service(i["Name"].lstrip("/"))
    ]
    summary = f"{len(events)} container lifecycle events in last {window_minutes}m; containers with restarts: {[r['container'] for r in restarted] or 'none'}"
    lines = [f"{e['time']} {e['container']} {e['event']}" for e in events[-30:]]
    return ToolOutput(text="\n".join([summary, *lines]), facts=[Fact(signal=Signal.DEPLOY, summary=summary, data={"events": events[-30:], "restarted": restarted})])
