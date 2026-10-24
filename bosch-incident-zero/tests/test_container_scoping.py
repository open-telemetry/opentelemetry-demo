"""Regression tests for Docker container scoping and health inspection."""
from __future__ import annotations

import json
from typing import Any, Dict, List
import pytest

from src.agent.tools import (
    DEMO_CONTAINERS,
    EXCLUDED_SERVICES,
    ToolContext,
    _container_states,
    _discover_compose_project,
    _scoped_container_names,
    container_health,
    system_overview,
)


def _make_inspect_container(name: str, status: str = "running", restart_count: int = 0,
                            exit_code: int = 0, oom_killed: bool = False,
                            health_status: str = "healthy", project: str = "opentelemetry-demo") -> Dict[str, Any]:
    return {
        "Name": f"/{name}",
        "State": {
            "Status": status,
            "ExitCode": exit_code,
            "OOMKilled": oom_killed,
            "Health": {"Status": health_status},
            "StartedAt": "2026-10-23T18:00:00Z",
        },
        "RestartCount": restart_count,
        "Config": {
            "Labels": {
                "com.docker.compose.project": project,
                "com.docker.compose.service": name,
            }
        },
    }


def _make_ps_row(name: str, state: str = "running", status: str = "Up 10 minutes",
                 project: str = "opentelemetry-demo") -> Dict[str, Any]:
    return {
        "Names": name,
        "State": state,
        "Status": status,
        "Labels": f"com.docker.compose.project={project},com.docker.compose.service={name}",
    }


class _MockDockerRunner:
    def __init__(self, ps_rows: List[Dict[str, Any]], inspect_map: Dict[str, Dict[str, Any]],
                 should_raise: bool = False) -> None:
        self.ps_rows = ps_rows
        self.inspect_map = inspect_map
        self.should_raise = should_raise
        self.calls: List[List[str]] = []

    def __call__(self, args: List[str]) -> str:
        self.calls.append(args)
        if self.should_raise:
            raise RuntimeError("docker daemon unavailable")

        cmd = args[0] if args else ""
        if cmd == "inspect":
            if "--format" in args:
                # anchor inspect
                target = args[-1]
                if target in self.inspect_map:
                    labels = self.inspect_map[target].get("Config", {}).get("Labels", {})
                    return json.dumps(labels)
                raise RuntimeError(f"No such object: {target}")
            # inspect *names
            targets = [a for a in args[1:] if not a.startswith("-")]
            found = []
            for t in targets:
                if t in self.inspect_map:
                    found.append(self.inspect_map[t])
                else:
                    raise RuntimeError(f"Error: No such object: {t}")
            return json.dumps(found)

        if cmd == "ps":
            # Check if filtered
            filter_val = None
            for i, a in enumerate(args):
                if a == "--filter" and i + 1 < len(args):
                    filter_val = args[i + 1]
            rows = self.ps_rows
            if filter_val and "label=com.docker.compose.project=" in filter_val:
                expected_proj = filter_val.split("=", 2)[-1]
                rows = [r for r in rows if f"com.docker.compose.project={expected_proj}" in r.get("Labels", "")]
            if "--format" in args:
                fmt_idx = args.index("--format") + 1
                fmt = args[fmt_idx]
                if fmt == "{{.Names}}":
                    return "\n".join(r["Names"] for r in rows)
                if fmt == "{{json .}}":
                    return "\n".join(json.dumps(r) for r in rows)
            return "\n".join(r["Names"] for r in rows)

        raise RuntimeError(f"Unhandled mock docker command: {args}")


def _mock_ctx(ps_rows: List[Dict[str, Any]], inspect_map: Dict[str, Dict[str, Any]],
              should_raise: bool = False) -> ToolContext:
    runner = _MockDockerRunner(ps_rows, inspect_map, should_raise=should_raise)
    return ToolContext(
        prometheus=type("P", (), {"query": lambda self, q: {"data": {"result": []}}})(),
        jaeger=object(),
        opensearch=object(),
        docker_runner=runner,
    )


def test_scoped_container_names_filters_unrelated_containers():
    ps = [
        _make_ps_row("frontend"),
        _make_ps_row("checkout"),
        _make_ps_row("railway-backend", project="railway"),
        _make_ps_row("nice_beaver", project="other"),
        _make_ps_row("flagd"),  # excluded service
    ]
    inspect_map = {
        "frontend": _make_inspect_container("frontend"),
        "checkout": _make_inspect_container("checkout"),
    }
    ctx = _mock_ctx(ps, inspect_map)
    names = _scoped_container_names(ctx)
    assert "frontend" in names
    assert "checkout" in names
    assert "railway-backend" not in names
    assert "nice_beaver" not in names
    assert "flagd" not in names


def test_container_health_healthy_demo_container():
    ps = [_make_ps_row("checkout")]
    inspect_map = {"checkout": _make_inspect_container("checkout", status="running", restart_count=0)}
    ctx = _mock_ctx(ps, inspect_map)
    res = container_health(ctx, "checkout")
    assert res["status"] == "ok"
    assert res["data"]["containers"][0]["name"] == "checkout"
    assert res["data"]["containers"][0]["state"] == "running"
    assert "All 1 inspected container(s) running" in res["summary"]


def test_container_health_stopped_or_unhealthy_demo_container():
    ps = [_make_ps_row("cart", state="exited", status="Exited (1) 2 minutes ago")]
    inspect_map = {"cart": _make_inspect_container("cart", status="exited", exit_code=1, restart_count=3)}
    ctx = _mock_ctx(ps, inspect_map)
    res = container_health(ctx, "cart")
    assert res["status"] == "ok"
    assert res["data"]["containers"][0]["name"] == "cart"
    assert res["data"]["containers"][0]["state"] == "exited"
    assert res["data"]["containers"][0]["restart_count"] == 3
    assert "Unhealthy/restarted: cart" in res["summary"]


def test_unrelated_unhealthy_container_not_reported_as_bosch_incident():
    # Host has an unrelated stopped container (e.g. railway-backend) alongside healthy frontend
    ps = [
        _make_ps_row("frontend", state="running"),
        _make_ps_row("railway-backend", state="exited", status="Exited (255) 4 days ago", project="railway"),
    ]
    inspect_map = {
        "frontend": _make_inspect_container("frontend"),
        "railway-backend": _make_inspect_container("railway-backend", status="exited", exit_code=255, project="railway"),
    }
    ctx = _mock_ctx(ps, inspect_map)

    # 1. Global container_health query must not report railway-backend
    res = container_health(ctx)
    assert res["status"] == "ok"
    reported_names = [c["name"] for c in res["data"]["containers"]]
    assert "frontend" in reported_names
    assert "railway-backend" not in reported_names
    assert "railway-backend" not in res["summary"]

    # 2. Explicit query on railway-backend informs that it is not part of the demo
    explicit_res = container_health(ctx, "railway-backend")
    assert explicit_res["status"] == "ok"
    assert "not part of the OpenTelemetry Demo" in explicit_res["summary"]
    assert explicit_res["data"]["containers"] == []


def test_missing_or_inaccessible_docker_data():
    ctx = _mock_ctx([], {}, should_raise=True)
    res = container_health(ctx)
    assert res["status"] == "source_unavailable"
    assert "Docker unavailable" in res["summary"]

    states, err = _container_states(ctx)
    assert states is None
    assert "docker daemon unavailable" in err


def test_empty_container_results_not_reported_as_healthy():
    ctx = _mock_ctx([], {})
    res = container_health(ctx)
    assert res["status"] == "no_data"
    assert "No monitored demo containers found" in res["summary"]


def test_fallback_when_label_discovery_unavailable():
    # When compose project label is absent, fallback to known DEMO_CONTAINERS identities
    ps = [
        {"Names": "payment", "State": "running", "Status": "Up 5m", "Labels": ""},
        {"Names": "random-host-app", "State": "exited", "Status": "Exited (1)", "Labels": ""},
    ]
    inspect_map = {
        "payment": {
            "Name": "/payment",
            "State": {"Status": "running", "ExitCode": 0, "OOMKilled": False, "Health": {"Status": "healthy"}},
            "RestartCount": 0,
            "Config": {"Labels": {}},
        }
    }
    ctx = _mock_ctx(ps, inspect_map)
    names = _scoped_container_names(ctx)
    assert names == ["payment"]
    assert "random-host-app" not in names

    res = container_health(ctx)
    assert res["status"] == "ok"
    assert len(res["data"]["containers"]) == 1
    assert res["data"]["containers"][0]["name"] == "payment"

def test_same_named_container_from_unrelated_project_is_rejected():
    # Another project has a container named 'checkout' (which matches DEMO_CONTAINERS),
    # but belongs to project 'unrelated-project'.
    ps = [
        _make_ps_row("frontend", project="opentelemetry-demo"),
        _make_ps_row("checkout", project="unrelated-project"),
    ]
    inspect_map = {
        "frontend": _make_inspect_container("frontend", project="opentelemetry-demo"),
        "checkout": _make_inspect_container("checkout", status="exited", exit_code=137, project="unrelated-project"),
    }
    ctx = _mock_ctx(ps, inspect_map)

    # 1. Scoped container names must NOT include the unrelated 'checkout'
    names = _scoped_container_names(ctx)
    assert "frontend" in names
    assert "checkout" not in names

    # 2. Bulk health check must NOT report the unrelated 'checkout'
    res = container_health(ctx)
    assert res["status"] == "ok"
    reported_names = [c["name"] for c in res["data"]["containers"]]
    assert "frontend" in reported_names
    assert "checkout" not in reported_names

    # 3. Explicit query on 'checkout' must verify project membership and reject it
    explicit_res = container_health(ctx, "checkout")
    assert explicit_res["status"] == "ok"
    assert "not part of the OpenTelemetry Demo" in explicit_res["summary"]
    assert explicit_res["data"]["containers"] == []


def test_container_states_rejects_unrelated_project_same_named_container():
    ps = [
        _make_ps_row("frontend", project="opentelemetry-demo"),
        _make_ps_row("checkout", project="unrelated-project"),
    ]
    inspect_map = {
        "frontend": _make_inspect_container("frontend", project="opentelemetry-demo"),
        "checkout": _make_inspect_container("checkout", project="unrelated-project"),
    }
    ctx = _mock_ctx(ps, inspect_map)

    states, err = _container_states(ctx)
    assert err is None
    assert states is not None
    assert "frontend" in states
    assert "checkout" not in states
