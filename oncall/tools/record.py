"""CLI for recording telemetry fixtures from live backends.

Usage:
    python -m oncall.tools.record --scenario baseline

Records the exact queries the tools make (get_metrics PROMQL for every metric,
service-wide and per service, now and baseline; error and all traces; error and
warn logs) plus a trimmed docker inspect/stats snapshot for container_health
and deploy_history. Replay matches on backends.fixture_key().
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime

from oncall.config import load_settings
from oncall.models import FLAG_REDACTED, scrub_flags
from oncall.platform import containers
from oncall.safety.exclusions import FIXTURE_SCRUB, is_excluded
from oncall.tools.backends import BackendError, RecordingBackend
from oncall.tools.metrics import PROMQL, _build_promql

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASELINE_OFFSET_S = 30 * 60
TRACE_LIMIT = 20
ALL_TRACES_LIMIT = 5
LOG_LIMIT = 200
LOG_LEVELS = ("error", "warn")


def _metrics() -> list[str]:
    return sorted({name.rsplit("_", 1)[0] for name in PROMQL})


def _trim_inspect(info: dict) -> dict:
    labels = (info.get("Config") or {}).get("Labels") or {}
    host = info.get("HostConfig") or {}
    return {
        "Id": info.get("Id"),
        "Name": info.get("Name"),
        "Image": info.get("Image"),
        "Created": info.get("Created"),
        "RestartCount": info.get("RestartCount"),
        "State": info.get("State"),
        "HostConfig": {
            k: host.get(k) for k in ("NanoCpus", "CpuQuota", "CpuPeriod", "Memory")
        },
        "Config": {
            "Image": (info.get("Config") or {}).get("Image"),
            "Labels": {
                k: v for k, v in labels.items() if k == "com.docker.compose.service"
            },
        },
    }


def record_docker(backend: RecordingBackend) -> int:
    """Write container_health.json (inspect + stats) for the offline tools."""
    settings = load_settings()
    infos = [
        i
        for i in containers.inspect_containers(
            containers.compose_container_ids(settings.COMPOSE_PROJECT_NAME)
        )
        if not is_excluded((i.get("Name") or "").lstrip("/"))
    ]
    running = [
        i["Id"] for i in infos if (i.get("State") or {}).get("Status") == "running"
    ]
    fixture = {
        "captured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inspect": [_trim_inspect(i) for i in infos],
        "stats": containers._stats(running),
        "deploy_snapshot": None,
    }
    text = json.dumps(scrub_flags(fixture), indent=1, sort_keys=True)
    path = backend.scenario_dir / containers.FIXTURE_FILE
    path.write_text(FIXTURE_SCRUB.sub(FLAG_REDACTED, text), encoding="utf-8")
    return len(infos)


def record_scenario(
    scenario: str = "baseline",
    services: Sequence[str] | None = None,
    backend: RecordingBackend | None = None,
) -> int:
    """Record every query the tools make for a scenario; returns calls recorded."""
    if backend is None:
        backend = RecordingBackend(scenario=scenario)
    logger.info("Recording scenario '%s' to %s", scenario, backend.scenario_dir)

    recorded = errors = 0

    def call(fn, *args, **kwargs) -> None:
        nonlocal recorded, errors
        try:
            fn(*args, **kwargs)
            recorded += 1
        except BackendError as exc:
            errors += 1
            logger.warning("%s%s failed: %s", fn.__name__, args, exc)

    targets = list(services or backend.jaeger_services())
    baseline_at = str(int(time.time() - BASELINE_OFFSET_S))
    for metric in _metrics():
        for svc in [None, *targets]:
            promql = _build_promql(metric, svc, "5m")
            call(backend.prom_query, promql)
            call(backend.prom_query, promql, at=baseline_at)
    for svc in targets:
        call(backend.jaeger_traces, svc, "15m", TRACE_LIMIT, {"error": "true"})
        call(backend.jaeger_traces, svc, "15m", ALL_TRACES_LIMIT, None)
    for level in LOG_LEVELS:
        for svc in [None, *targets]:
            call(backend.logs_search, svc, level, 15, LOG_LIMIT)
    try:
        logger.info("Recorded docker state of %d containers", record_docker(backend))
        recorded += 1
    except containers.DockerError as exc:
        errors += 1
        logger.warning("docker snapshot failed: %s", exc)

    logger.info(
        "Finished recording '%s': %d calls recorded, %d errors",
        scenario,
        recorded,
        errors,
    )
    return recorded


def main() -> None:
    parser = argparse.ArgumentParser(description="Record telemetry fixtures.")
    parser.add_argument(
        "--scenario",
        default="baseline",
        help="Name of scenario / folder to store fixtures in.",
    )
    args = parser.parse_args()
    if record_scenario(scenario=args.scenario) == 0:
        logger.error("No queries were recorded successfully.")
        sys.exit(1)


if __name__ == "__main__":
    main()
