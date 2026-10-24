import json
import subprocess
from datetime import UTC, datetime
from unittest import mock

import pytest

from oncall.platform import containers, deploys
from oncall.platform.deploys import find_changes, take_snapshot
from oncall.tools import TOOL_SCHEMAS, TOOLS

NOW = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
OLD = "2026-10-23T08:00:00.123456789Z"  # 4 hours before NOW


def _inspect(
    name: str,
    created: str = OLD,
    started: str = OLD,
    image_id: str = "sha256:aaaaaaaaaaaa1111",
) -> dict:
    """A trimmed `docker inspect` entry with only the fields the tool reads."""
    return {
        "Id": f"{name}-id",
        "Name": f"/{name}",
        "Created": created,
        "Image": image_id,
        "State": {"Status": "running", "StartedAt": started},
        "Config": {"Image": f"ghcr.io/open-telemetry/demo:latest-{name}"},
    }


@pytest.fixture
def runs_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEMETRY_BACKEND", "live")
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    return tmp_path


def _fake_docker(infos: list[dict]):
    """Fake subprocess.run answering `compose ps` and `inspect` with canned output."""
    outputs = {
        "ps": "\n".join(i["Id"] for i in infos),
        "inspect": json.dumps(infos),
    }

    def run(cmd, **kwargs):
        sub = containers._subcommand(cmd[1:])
        return subprocess.CompletedProcess(cmd, 0, stdout=outputs[sub], stderr="")

    return mock.patch("oncall.platform.containers.subprocess.run", side_effect=run)


def test_restart_in_window():
    infos = [_inspect("cart", started="2026-10-23T11:50:00Z"), _inspect("email")]
    result = find_changes(infos, None, 60, NOW)
    assert result["ok"] is True
    assert result["summary"] == (
        "1 container change(s) in the last 60 min (derived from container start "
        "times; no deploy system available): cart restarted at 2026-10-23T11:50:00Z"
    )
    evidence = result["evidence"][0]
    assert evidence["id"] == "deploy:cart@2026-10-23T11:50:00Z"
    assert "image ghcr.io/open-telemetry/demo:latest-cart" in evidence["text"]


def test_created_in_window():
    infos = [
        _inspect("ad", created="2026-10-23T11:40:00Z", started="2026-10-23T11:40:01Z")
    ]
    result = find_changes(infos, None, 60, NOW)
    assert "ad created at 2026-10-23T11:40:01Z" in result["summary"]


def test_new_container_not_in_snapshot():
    infos = [
        _inspect("ad", created="2026-10-23T11:40:00Z", started="2026-10-23T11:40:01Z")
    ]
    result = find_changes(infos, {"cart": "sha256:x"}, 60, NOW)
    assert "ad new container at" in result["summary"]


def test_image_change_against_snapshot():
    infos = [
        _inspect(
            "payment",
            created="2026-10-23T11:55:00Z",
            started="2026-10-23T11:55:02Z",
            image_id="sha256:bbbbbbbbbbbb2222",
        )
    ]
    snapshot = {"payment": "sha256:aaaaaaaaaaaa1111"}
    result = find_changes(infos, snapshot, 60, NOW)
    assert "payment image changed aaaaaaaaaaaa -> bbbbbbbbbbbb" in result["summary"]


def test_nothing_in_window_is_a_valid_answer():
    result = find_changes([_inspect("cart"), _inspect("ad")], None, 60, NOW)
    assert result["ok"] is True
    assert result["evidence"] == []
    assert result["summary"].startswith("No container changes in the last 60 min")


def test_window_limits_what_is_reported():
    infos = [_inspect("cart", started="2026-10-23T10:30:00Z")]  # 90 min ago
    assert find_changes(infos, None, 60, NOW)["evidence"] == []
    assert len(find_changes(infos, None, 120, NOW)["evidence"]) == 1


def test_newest_change_first():
    infos = [
        _inspect("cart", started="2026-10-23T11:10:00Z"),
        _inspect("ad", started="2026-10-23T11:50:00Z"),
    ]
    result = find_changes(infos, None, 60, NOW)
    assert [e["id"].split("@")[0] for e in result["evidence"]] == [
        "deploy:ad",
        "deploy:cart",
    ]


def test_live_first_call_writes_snapshot_then_detects_image_change(runs_dir):
    before = [_inspect("cart")]
    with _fake_docker(before):
        first = TOOLS["deploy_history"]()
    assert first["summary"].startswith("No image snapshot existed")
    snapshot = json.loads((runs_dir / "deploy_snapshot.json").read_text())
    assert snapshot == {"cart": "sha256:aaaaaaaaaaaa1111"}

    after = [_inspect("cart", image_id="sha256:cccccccccccc3333")]
    with _fake_docker(after):
        second = TOOLS["deploy_history"](window_min=30)
    assert "cart image changed aaaaaaaaaaaa -> cccccccccccc" in second["summary"]
    assert second["query"] == {"window_min": 30}


def test_take_snapshot(runs_dir):
    with _fake_docker([_inspect("cart"), _inspect("ad")]):
        assert take_snapshot() is True
    snapshot = json.loads((runs_dir / "deploy_snapshot.json").read_text())
    assert set(snapshot) == {"cart", "ad"}


def test_take_snapshot_docker_down_returns_false(runs_dir):
    with mock.patch(
        "oncall.platform.containers.subprocess.run",
        side_effect=FileNotFoundError("docker"),
    ):
        assert take_snapshot() is False
    assert not (runs_dir / "deploy_snapshot.json").exists()


def test_docker_down_returns_error(runs_dir):
    down = subprocess.CompletedProcess([], 1, stdout="", stderr="Cannot connect")
    with mock.patch("oncall.platform.containers.subprocess.run", return_value=down):
        result = TOOLS["deploy_history"]()
    assert result["ok"] is False
    assert "Docker not reachable" in result["error"]


def test_non_positive_window_is_rejected(runs_dir):
    result = TOOLS["deploy_history"](window_min=0)
    assert result["ok"] is False
    assert "positive" in result["error"]


def test_offline_reads_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEMETRY_BACKEND", "offline")
    monkeypatch.setenv("OFFLINE_DIR", str(tmp_path))
    fixture = {
        "captured_at": "2026-10-23T12:00:00Z",
        "inspect": [_inspect("cart", started="2026-10-23T11:58:00Z")],
        "deploy_snapshot": {"cart": "sha256:aaaaaaaaaaaa1111"},
    }
    (tmp_path / "baseline").mkdir()
    (tmp_path / "baseline" / "container_health.json").write_text(json.dumps(fixture))
    with mock.patch("oncall.platform.containers.subprocess.run") as run:
        result = TOOLS["deploy_history"]()
    run.assert_not_called()
    assert "cart restarted at 2026-10-23T11:58:00Z" in result["summary"]


def test_offline_without_fixture_is_not_available(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEMETRY_BACKEND", "offline")
    monkeypatch.setenv("OFFLINE_DIR", str(tmp_path))
    result = TOOLS["deploy_history"]()
    assert result["error"] == "deploy_history not available offline"


def test_reuses_container_health_docker_helper():
    # F08 must not run docker itself; all calls go through F07's read-only helper.
    assert "subprocess" not in deploys.__dict__


def test_tool_is_registered():
    schema = TOOL_SCHEMAS["deploy_history"]["input_schema"]
    assert schema["properties"]["window_min"]["type"] == ["integer", "null"]
    assert schema["required"] == []
