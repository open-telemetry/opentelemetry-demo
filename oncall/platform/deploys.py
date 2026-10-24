"""deploy_history tool: what changed in the demo's containers recently.

The demo has no deploy system, so changes are derived from Docker: when each
container was created and last started, and whether its image differs from a
snapshot taken when the agent started. Read-only: it reuses container_health's
docker helpers, which can only run `ps`, `inspect` and `stats`.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from oncall.config import Settings, load_settings
from oncall.models import Evidence, ToolResult, make_error, make_result

# Imported as a module (not `from ... import name`) to avoid a circular import:
# oncall.tools imports both tool modules while they are still loading.
from oncall.platform import containers
from oncall.tools.registry import register_tool

log = logging.getLogger(__name__)

TOOL = "deploy_history"
SOURCE_NOTE = "derived from container start times; no deploy system available"
SNAPSHOT_FILE = "deploy_snapshot.json"


def _name(info: dict) -> str:
    return (info.get("Name") or "").lstrip("/")


def _short_id(image_id: str | None) -> str:
    """sha256:4f1e...  ->  4f1e2a3b4c5d (12 chars, like `docker images`)."""
    return (image_id or "").removeprefix("sha256:")[:12]


def snapshot_path(settings: Settings) -> Path:
    return Path(settings.RUNS_DIR) / SNAPSHOT_FILE


def read_snapshot(path: Path) -> dict[str, str] | None:
    """{container name: image id} from an earlier snapshot, or None if there is none."""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_snapshot(infos: list[dict], path: Path) -> dict[str, str]:
    """Record each container's current image id, to spot image changes later."""
    snapshot = {_name(i): i.get("Image") for i in infos}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot


def take_snapshot(settings: Settings | None = None) -> bool:
    """Snapshot image ids at agent start. Returns False (never raises) on failure."""
    settings = settings or load_settings()
    try:
        ids = containers.compose_container_ids(settings.COMPOSE_PROJECT_NAME)
        infos = containers.inspect_containers(ids)
    except containers.DockerError as exc:
        log.warning("deploy snapshot not taken: %s", exc)
        return False
    write_snapshot(infos, snapshot_path(settings))
    return True


def _change(
    info: dict, snapshot: dict[str, str] | None, since: datetime
) -> dict | None:
    """The most important change to one container since `since`, or None.

    Image change beats created, which beats restarted.
    """
    name = _name(info)
    state = info.get("State") or {}
    started_at = state.get("StartedAt")
    created = containers.parse_docker_time(info.get("Created"))
    started = containers.parse_docker_time(started_at)
    old_image = (snapshot or {}).get(name)
    new_image = info.get("Image")

    if old_image and new_image and old_image != new_image:
        kind = f"image changed {_short_id(old_image)} -> {_short_id(new_image)}"
    elif created and created >= since:
        kind = "new container" if snapshot and name not in snapshot else "created"
    elif started and started >= since:
        kind = "restarted"
    else:
        return None
    return {
        "name": name,
        "kind": kind,
        "at": started_at,
        "when": started or created,
        "image": (info.get("Config") or {}).get("Image"),
        "created_at": info.get("Created"),
    }


def find_changes(
    infos: list[dict],
    snapshot: dict[str, str] | None,
    window_min: int,
    now: datetime,
    note: str = "",
) -> ToolResult:
    """Turn raw `docker inspect` output into a ToolResult of recent changes."""
    query = {"window_min": window_min}
    since = now - timedelta(minutes=window_min)
    changes = [c for c in (_change(i, snapshot, since) for i in infos) if c]
    changes.sort(key=lambda c: c["when"] or since, reverse=True)  # newest first

    if changes:
        summary = (
            f"{len(changes)} container change(s) in the last {window_min} min "
            f"({SOURCE_NOTE}): "
            + "; ".join(f"{c['name']} {c['kind']} at {c['at']}" for c in changes)
        )
    else:
        summary = f"No container changes in the last {window_min} min ({SOURCE_NOTE})."
    if note:
        summary = f"{note} {summary}"

    ts = now.isoformat(timespec="seconds")
    evidence: list[Evidence] = [
        {
            "id": f"deploy:{c['name']}@{c['at']}",
            "text": (
                f"{c['name']}: {c['kind']} at {c['at']} "
                f"(container created {c['created_at']}), image {c['image']}"
            ),
            "ts": ts,
        }
        for c in changes
    ]
    return make_result(TOOL, query, summary, evidence)


@register_tool(
    TOOL,
    "Containers restarted, recreated or given a new image in the last "
    "window_min minutes (from Docker start times). Empty = nothing changed.",
    {
        "properties": {
            "window_min": {
                "type": "integer",
                "default": 60,
            }
        }
    },
)
def deploy_history(window_min: int = 60) -> ToolResult:
    """Report container restarts, recreations and image changes in the window."""
    settings = load_settings()
    query = {"window_min": window_min}
    if window_min <= 0:
        return make_error(
            TOOL, query, "window_min must be a positive number of minutes"
        )
    try:
        if settings.TELEMETRY_BACKEND == "offline":
            fixture = containers.load_fixture(settings)
            if fixture is None:
                return make_error(TOOL, query, "deploy_history not available offline")
            now = containers.parse_docker_time(
                fixture.get("captured_at")
            ) or datetime.now(UTC)
            return find_changes(
                fixture.get("inspect", []),
                fixture.get("deploy_snapshot"),
                window_min,
                now,
            )

        ids = containers.compose_container_ids(settings.COMPOSE_PROJECT_NAME)
        infos = containers.inspect_containers(ids)
        path = snapshot_path(settings)
        snapshot = read_snapshot(path)
        note = ""
        if snapshot is None:
            write_snapshot(infos, path)
            note = "No image snapshot existed, so image changes can't be shown yet."
        return find_changes(infos, snapshot, window_min, datetime.now(UTC), note)
    except containers.DockerError as exc:
        return make_error(TOOL, query, f"Docker not reachable: {exc}")
