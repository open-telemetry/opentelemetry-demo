import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

import pytest

from oncall.platform import containers
from oncall.platform.containers import DockerError, check_containers
from oncall.tools import TOOL_SCHEMAS, TOOLS

NOW = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)


def _inspect(
    name: str,
    status: str = "running",
    restarts: int = 0,
    oom: bool = False,
    exit_code: int = 0,
    started_at: str = "2026-10-23T09:00:00.123456789Z",
    health: str | None = None,
    nano_cpus: int = 0,
) -> dict:
    """A trimmed `docker inspect` entry with only the fields the tool reads."""
    state = {
        "Status": status,
        "OOMKilled": oom,
        "ExitCode": exit_code,
        "StartedAt": started_at,
    }
    if health:
        state["Health"] = {"Status": health}
    return {
        "Id": f"{name}-id",
        "Name": f"/{name}",
        "RestartCount": restarts,
        "State": state,
        "HostConfig": {"NanoCpus": nano_cpus, "CpuQuota": 0, "CpuPeriod": 0},
        "Config": {"Labels": {"com.docker.compose.service": name}},
    }


def _stats(name: str, cpu: str = "1.50%", mem: str = "20.00%") -> dict:
    return {"Name": name, "ID": f"{name}-id", "CPUPerc": cpu, "MemPerc": mem}


def test_all_healthy():
    infos = [_inspect("cart"), _inspect("payment")]
    stats = [_stats("cart"), _stats("payment")]
    result = check_containers(infos, stats, None, NOW)
    assert result["ok"] is True
    assert result["summary"].startswith("All 2 containers healthy. Busiest: cart")
    assert [e["id"] for e in result["evidence"]] == [
        "container:cart",
        "container:payment",
    ]
    assert "FLAGGED" not in result["evidence"][0]["text"]


def test_stopped_container_is_flagged_first():
    infos = [_inspect("ad"), _inspect("payment", status="exited", exit_code=137)]
    result = check_containers(infos, [_stats("ad")], None, NOW)
    assert result["summary"].startswith("1 of 2 containers unhealthy: payment")
    assert result["evidence"][0]["id"] == "container:payment"
    assert "not running (state=exited, exit_code=137)" in result["evidence"][0]["text"]


def test_oom_killed_is_flagged():
    infos = [_inspect("recommendation", status="exited", oom=True, exit_code=137)]
    result = check_containers(infos, [], None, NOW)
    text = result["evidence"][0]["text"]
    assert "oom_killed=true" in text
    assert "OOM-killed" in text


def test_high_cpu_is_measured_against_the_cpu_limit():
    # 48% of one core is 96% of a 0.5-core limit.
    limited = _inspect("ad", nano_cpus=500_000_000)
    unlimited = _inspect("cart")
    stats = [_stats("ad", cpu="48.00%"), _stats("cart", cpu="48.00%")]
    result = check_containers([limited, unlimited], stats, None, NOW)
    assert result["summary"].startswith(
        "1 of 2 containers unhealthy: ad (CPU 96% of limit)."
    )
    texts = {e["id"]: e["text"] for e in result["evidence"]}
    assert "cpu=96.0% of limit" in texts["container:ad"]
    assert "cpu=48.0% of one core" in texts["container:cart"]


def test_busy_container_without_cpu_limit_is_not_flagged():
    # Live demo: no container has a CPU limit and busy ones use several cores.
    stats = [_stats("product-catalog", cpu="418.00%")]
    result = check_containers([_inspect("product-catalog")], stats, None, NOW)
    assert result["summary"].startswith("All 1 containers healthy.")


def test_high_memory_is_reported_but_not_flagged():
    # Live demo: checkout runs at ~98% of its 20 MiB limit while healthy.
    result = check_containers(
        [_inspect("checkout")], [_stats("checkout", mem="98.14%")], None, NOW
    )
    assert result["summary"].startswith("All 1 containers healthy.")
    assert "mem=98.1% of limit" in result["evidence"][0]["text"]


def test_recent_restarts_are_flagged_but_old_ones_are_not():
    recent = _inspect("cart", restarts=7, started_at="2026-10-23T11:58:00Z")
    old = _inspect("email", restarts=1, started_at="2026-10-23T08:00:00Z")
    result = check_containers([recent, old], [], None, NOW)
    assert result["summary"] == (
        "1 of 2 containers unhealthy: cart (restarted 7 times, last start 2 min ago)"
    )


def test_restarting_state_is_flagged():
    infos = [_inspect("cart", status="restarting", restarts=3, exit_code=1)]
    result = check_containers(infos, [], None, NOW)
    assert "not running (state=restarting, exit_code=1)" in result["summary"]


def test_unhealthy_healthcheck_is_flagged():
    infos = [_inspect("frontend", health="unhealthy")]
    result = check_containers(infos, [_stats("frontend")], None, NOW)
    assert "healthcheck unhealthy" in result["summary"]


def test_service_filter():
    infos = [_inspect("cart"), _inspect("payment")]
    result = check_containers(infos, [], "payment", NOW)
    assert [e["id"] for e in result["evidence"]] == ["container:payment"]
    assert result["query"] == {"service": "payment"}


def test_unknown_service_lists_known_ones():
    result = check_containers([_inspect("cart")], [], "nope", NOW)
    assert result["ok"] is False
    assert "Known services: cart" in result["error"]


def test_no_containers_means_demo_not_running():
    result = check_containers([], [], None, NOW)
    assert result["ok"] is True
    assert "No demo containers found" in result["summary"]


def _fake_docker(outputs: dict[str, str]):
    """Fake subprocess.run answering each docker subcommand with canned stdout."""

    def run(cmd, **kwargs):
        sub = containers._subcommand(cmd[1:])
        return subprocess.CompletedProcess(cmd, 0, stdout=outputs[sub], stderr="")

    return run


def test_live_run_through_registry_uses_only_read_only_commands(monkeypatch):
    monkeypatch.setenv("TELEMETRY_BACKEND", "live")
    infos = [_inspect("cart"), _inspect("payment", status="exited", exit_code=1)]
    outputs = {
        "ps": "cart-id\npayment-id\n",
        "inspect": json.dumps(infos),
        "stats": json.dumps(_stats("cart")) + "\n",
    }
    with mock.patch(
        "oncall.platform.containers.subprocess.run", side_effect=_fake_docker(outputs)
    ) as run:
        result = TOOLS["container_health"]()
    assert result["ok"] is True
    assert result["evidence"][0]["id"] == "container:payment"
    subcommands = [containers._subcommand(c.args[0][1:]) for c in run.call_args_list]
    assert subcommands == ["ps", "inspect", "stats"]
    # Only the running container is passed to docker stats.
    assert run.call_args_list[2].args[0][-1] == "cart-id"


def test_docker_daemon_down_returns_error(monkeypatch):
    monkeypatch.setenv("TELEMETRY_BACKEND", "live")
    down = subprocess.CompletedProcess([], 1, stdout="", stderr="Cannot connect")
    with mock.patch("oncall.platform.containers.subprocess.run", return_value=down):
        result = TOOLS["container_health"]()
    assert result["ok"] is False
    assert "Docker not reachable" in result["error"]
    assert "Cannot connect" in result["error"]


def test_docker_not_installed_returns_error(monkeypatch):
    monkeypatch.setenv("TELEMETRY_BACKEND", "live")
    with mock.patch(
        "oncall.platform.containers.subprocess.run",
        side_effect=FileNotFoundError("docker"),
    ):
        result = TOOLS["container_health"](service="cart")
    assert result["ok"] is False
    assert result["query"] == {"service": "cart"}


@pytest.mark.parametrize(
    "args",
    [
        ["restart", "cart"],
        ["stop", "cart"],
        ["compose", "-f", "compose.yaml", "up", "-d"],
        ["rm", "--filter", "ps"],
    ],
)
def test_write_commands_are_refused(args):
    with (
        mock.patch("oncall.platform.containers.subprocess.run") as run,
        pytest.raises(DockerError, match="refusing"),
    ):
        containers._run_docker(args)
    run.assert_not_called()


def test_source_has_no_write_calls():
    source = Path(containers.__file__).read_text(encoding="utf-8")
    write_verbs = "start|stop|restart|kill|rm|remove|update|exec|run|pause|up|down"
    assert not re.search(rf'"({write_verbs})"', source)  # docker CLI verbs
    assert not re.search(rf"\.({write_verbs})\(", source.replace("subprocess.run(", ""))
    assert containers.READ_ONLY_COMMANDS == ("ps", "inspect", "stats")


def test_offline_without_fixture_is_not_available(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEMETRY_BACKEND", "offline")
    monkeypatch.setenv("OFFLINE_DIR", str(tmp_path))
    result = TOOLS["container_health"]()
    assert result["ok"] is False
    assert result["error"] == "container_health not available offline"


def test_offline_reads_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEMETRY_BACKEND", "offline")
    monkeypatch.setenv("OFFLINE_DIR", str(tmp_path))
    monkeypatch.setenv("OFFLINE_SCENARIO", "cart-down")
    fixture = {
        "captured_at": "2026-10-23T12:00:00Z",
        "inspect": [_inspect("cart", status="exited", exit_code=137)],
        "stats": [],
    }
    (tmp_path / "cart-down").mkdir()
    (tmp_path / "cart-down" / "container_health.json").write_text(json.dumps(fixture))
    with mock.patch("oncall.platform.containers.subprocess.run") as run:
        result = TOOLS["container_health"]()
    run.assert_not_called()
    assert result["summary"].startswith("1 of 1 containers unhealthy: cart")


def test_tool_is_registered_with_optional_service():
    schema = TOOL_SCHEMAS["container_health"]["input_schema"]
    assert "service" in schema["properties"]
    assert schema["required"] == []


def test_busiest_healthy_containers_survive_the_evidence_cap():
    # 25 healthy containers; the busy one sorts last by name but must be shown.
    names = [f"svc{i:02d}" for i in range(24)] + ["zz-recommendation"]
    infos = [_inspect(n) for n in names]
    stats = [_stats(n) for n in names[:-1]] + [
        _stats("zz-recommendation", mem="97.00%")
    ]
    result = check_containers(infos, stats, None, NOW)
    assert len(result["evidence"]) == 20
    assert result["evidence"][0]["id"] == "container:zz-recommendation"
    assert (
        "Busiest: zz-recommendation cpu=1.5% of one core, mem=97.0% of limit"
        in (result["summary"])
    )
