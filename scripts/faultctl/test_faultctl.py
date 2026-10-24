import json
from typing import ClassVar

import faultctl
import pytest

MIB = 1024 * 1024


def ctr(name, project=faultctl.PROJECT, running=True, health="healthy", **hc):
    host_config = {
        "NanoCpus": 0,
        "CpuQuota": 0,
        "CpuPeriod": 0,
        "Memory": 20 * MIB,
        "MemorySwap": 40 * MIB,
    }
    host_config.update(hc)
    return {
        "Name": f"/{name}",
        "Config": {
            "Labels": {
                "com.docker.compose.project": project,
                "com.docker.compose.service": name,
            }
        },
        "State": {
            "Running": running,
            "Status": "running" if running else "exited",
            "Health": {"Status": health},
        },
        "HostConfig": host_config,
    }


def to_bytes(value):
    return int(value[:-1]) * MIB if value.endswith("m") else int(value)


class FakeDocker(faultctl.Docker):
    """Applies docker CLI calls to in-memory inspect dicts (ids are names)."""

    FLAGS: ClassVar[dict] = {
        "--cpus": ("NanoCpus", lambda v: int(float(v) * 1e9)),
        "--cpu-quota": ("CpuQuota", int),
        "--cpu-period": ("CpuPeriod", int),
        "--memory": ("Memory", to_bytes),
        "--memory-swap": ("MemorySwap", to_bytes),
    }

    def __init__(self, *containers):
        self.c = {faultctl.name_of(c): c for c in containers}
        self.calls = []
        self.flagd_log = "filepath event: ./etc/flagd/demo.flagd.json WRITE"

    def run(self, args):
        self.calls.append(args)
        cmd = args[0]
        if cmd == "ps":
            project = args[-1].rsplit("=", 1)[1]
            return "\n".join(
                n
                for n, c in self.c.items()
                if c["Config"]["Labels"]["com.docker.compose.project"] == project
            )
        if cmd == "inspect":
            return json.dumps([self.c[i] for i in args[1:]])
        if cmd == "restart":
            self.c[args[-1]]["State"]["Running"] = True
            return ""
        c = self.c[args[-1]]
        if cmd in ("stop", "start"):
            c["State"]["Running"] = cmd == "start"
            c["State"]["Status"] = "running" if cmd == "start" else "exited"
        elif cmd == "update":
            opts = args[1:-1]
            for flag, value in zip(opts[::2], opts[1::2]):
                key, conv = self.FLAGS[flag]
                c["HostConfig"][key] = conv(value)
        return ""

    def logs(self, service, since):
        self.calls.append(["logs", service, since])
        return self.flagd_log

    def mutations(self):
        return [a for a in self.calls if a[0] in ("stop", "start", "update")]


SCENARIOS = {
    "scenario-06": {"type": "stop", "target": "valkey-cart", "params": {}},
    "scenario-08": {"type": "cpu_limit", "target": "currency", "params": {"cpus": 0.1}},
    "scenario-09": {
        "type": "mem_limit",
        "target": "email",
        "params": {"memory": "50m"},
    },
}


@pytest.fixture
def state(tmp_path):
    return tmp_path / ".state.json"


def do_reset(docker, state):
    return faultctl.reset(docker, state, wait_s=0, sleep=lambda s: None)


def test_shipped_scenarios_are_valid_and_neutral():
    scenarios = faultctl.load_scenarios()
    assert {"scenario-06", "scenario-07", "scenario-08", "scenario-09"} <= set(
        scenarios
    )
    assert all(sid.startswith("scenario-") for sid in scenarios)


@pytest.mark.parametrize(
    "body",
    [
        "scenarios: {s: {type: flag, target: x}}",
        "scenarios: {s: {type: stop}}",
        "scenarios: {s: {type: cpu_limit, target: x}}",
        "scenarios: {s: {type: mem_limit, target: x, params: {}}}",
    ],
)
def test_invalid_scenarios_rejected(tmp_path, body):
    path = tmp_path / "s.yaml"
    path.write_text(body)
    with pytest.raises(faultctl.FaultctlError):
        faultctl.load_scenarios(path)


def test_unknown_scenario_refused_without_docker_calls(state):
    docker = FakeDocker(ctr("valkey-cart"))
    with pytest.raises(faultctl.FaultctlError, match="unknown scenario"):
        faultctl.inject("scenario-99", docker, SCENARIOS, state)
    assert docker.calls == []


def test_target_outside_compose_project_refused(state):
    docker = FakeDocker(ctr("valkey-cart", project="other"))
    with pytest.raises(faultctl.FaultctlError, match="compose project"):
        faultctl.inject("scenario-06", docker, SCENARIOS, state)
    assert docker.mutations() == []


def test_stop_inject_status_reset(state):
    docker = FakeDocker(ctr("valkey-cart"), ctr("cart"))
    faultctl.inject("scenario-06", docker, SCENARIOS, state)
    assert docker.c["valkey-cart"]["State"]["Running"] is False
    assert json.loads(state.read_text())["injected"][0]["original"]["running"] is True
    lines = faultctl.status(docker, state)
    assert lines[0].startswith("scenario-06: stop on valkey-cart")
    assert "not healthy: valkey-cart: exited" in lines

    _, problems = do_reset(docker, state)
    assert problems == []
    assert docker.c["valkey-cart"]["State"]["Running"] is True
    assert not state.exists()
    assert faultctl.status(docker, state) == ["nothing injected"]


def test_same_scenario_twice_refused(state):
    docker = FakeDocker(ctr("valkey-cart"))
    faultctl.inject("scenario-06", docker, SCENARIOS, state)
    with pytest.raises(faultctl.FaultctlError, match="already injected"):
        faultctl.inject("scenario-06", docker, SCENARIOS, state)


def test_cpu_limit_uses_quota_and_reset_unlimits(state):
    docker = FakeDocker(ctr("currency"))
    faultctl.inject("scenario-08", docker, SCENARIOS, state)
    hc = docker.c["currency"]["HostConfig"]
    assert (hc["NanoCpus"], hc["CpuQuota"], hc["CpuPeriod"]) == (0, 10000, 100000)
    do_reset(docker, state)
    assert hc["CpuQuota"] == -1 and hc["NanoCpus"] == 0


def test_cpu_limit_with_existing_cpus_restores_it(state):
    docker = FakeDocker(ctr("currency", NanoCpus=2_000_000_000))
    faultctl.inject("scenario-08", docker, SCENARIOS, state)
    hc = docker.c["currency"]["HostConfig"]
    assert hc["NanoCpus"] == 100_000_000
    do_reset(docker, state)
    assert hc["NanoCpus"] == 2_000_000_000


def test_mem_limit_restored_exactly(state):
    docker = FakeDocker(ctr("email", Memory=100 * MIB, MemorySwap=200 * MIB))
    faultctl.inject("scenario-09", docker, SCENARIOS, state)
    hc = docker.c["email"]["HostConfig"]
    assert (hc["Memory"], hc["MemorySwap"]) == (50 * MIB, 50 * MIB)
    do_reset(docker, state)
    assert (hc["Memory"], hc["MemorySwap"]) == (100 * MIB, 200 * MIB)


def test_reset_is_idempotent(state):
    docker = FakeDocker(ctr("valkey-cart"), ctr("email"))
    faultctl.inject("scenario-06", docker, SCENARIOS, state)
    faultctl.inject("scenario-09", docker, SCENARIOS, state, combo=True)
    assert do_reset(docker, state)[1] == []
    docker.calls.clear()
    log, problems = do_reset(docker, state)
    assert (log, problems) == ([], [])
    assert docker.mutations() == []


def test_reset_starts_exited_project_containers_only(state):
    docker = FakeDocker(
        ctr("cart", running=False), ctr("xyz-worker", project="other", running=False)
    )
    log, problems = do_reset(docker, state)
    assert docker.c["cart"]["State"]["Running"] is True
    assert docker.c["xyz-worker"]["State"]["Running"] is False
    assert log == ["started exited container cart"] and problems == []


def test_reset_reports_unhealthy(state, monkeypatch):
    monkeypatch.setattr(faultctl, "STATE_PATH", state)
    docker = FakeDocker(ctr("cart", health="unhealthy"))
    _, problems = do_reset(docker, state)
    assert problems == ["cart: unhealthy"]
    assert faultctl.main(["reset", "--wait", "0"], docker=docker) == 1


def test_main_unknown_scenario_exit_code(capsys, monkeypatch, state):
    monkeypatch.setattr(faultctl, "STATE_PATH", state)
    assert faultctl.main(["inject", "scenario-99"], docker=FakeDocker()) == 2
    assert "unknown scenario" in capsys.readouterr().err


FLAG_TEXT = """{
  "flags": {
    "payFail": {
      "description": "pay",
      "state": "ENABLED",
      "variants": {"on": true, "off": false},
      "defaultVariant": "off"
    },
    "flood": {
      "state": "ENABLED",
      "variants": {
        "on": 100,
        "off": 0
      },
      "defaultVariant":   "off"
    }
  }
}
"""
FLAG_SCENARIOS = {
    "scenario-01": {
        "type": "flag",
        "target": "flagd",
        "params": {"key": "payFail", "variant": "on"},
    },
    "scenario-05": {
        "type": "flag",
        "target": "flagd",
        "params": {"key": "flood", "variant": "on"},
    },
    "scenario-77": {
        "type": "flag",
        "target": "flagd",
        "params": {"key": "nope", "variant": "on"},
    },
    "scenario-78": {
        "type": "flag",
        "target": "flagd",
        "params": {"key": "flood", "variant": "50"},
    },
    **SCENARIOS,
}


class FakeFlags(faultctl.FlagFile):
    """Flag file in a temp dir; 'git HEAD' is the text it was created with."""

    def __init__(self, tmp_path, text=FLAG_TEXT):
        super().__init__(tmp_path, "demo.flagd.json")
        self.head = text
        self.path.write_bytes(text.encode())
        self.restores = 0

    def modified(self):
        return self.read() != self.head

    def restore(self):
        self.restores += 1
        self.path.write_bytes(self.head.encode())


@pytest.fixture(autouse=True)
def clean_flag_file(monkeypatch, tmp_path):
    """Keep every test away from the real repo's flag file and git."""
    flags = FakeFlags(tmp_path)
    monkeypatch.setattr(faultctl, "FlagFile", lambda *a, **k: flags)
    return flags


def flagd():
    return ctr("flagd", health=None)


def test_flag_inject_edits_only_that_variant_and_keeps_formatting(
    state, clean_flag_file
):
    docker = FakeDocker(flagd())
    out = faultctl.inject(
        "scenario-05", docker, FLAG_SCENARIOS, state, sleep=lambda s: None
    )
    assert out == "injected scenario-05: flag set (flagd reloaded the flag file)"
    text = clean_flag_file.read()
    assert text == FLAG_TEXT.replace(
        '"defaultVariant":   "off"', '"defaultVariant":   "on"'
    )
    assert json.loads(text)["flags"]["payFail"]["defaultVariant"] == "off"
    saved = json.loads(state.read_text())["injected"][0]
    assert (saved["type"], saved["original"]) == ("flag", {"variant": "off"})
    assert docker.mutations() == []


def test_flag_inject_restarts_flagd_when_it_does_not_reload(state, clean_flag_file):
    docker = FakeDocker(flagd())
    docker.flagd_log = "nothing new"
    out = faultctl.inject(
        "scenario-01", docker, FLAG_SCENARIOS, state, sleep=lambda s: None
    )
    assert "restarted it" in out
    assert ["restart", "flagd"] in docker.calls


@pytest.mark.parametrize(
    ("sid", "error"), [("scenario-77", "not in"), ("scenario-78", "no variant")]
)
def test_unknown_flag_key_or_variant_refused_without_writing(
    state, clean_flag_file, sid, error
):
    docker = FakeDocker(flagd())
    with pytest.raises(faultctl.FaultctlError, match=error):
        faultctl.inject(sid, docker, FLAG_SCENARIOS, state, sleep=lambda s: None)
    assert clean_flag_file.read() == FLAG_TEXT


def test_reset_restores_flag_file_from_git_and_waits_for_reload(state, clean_flag_file):
    docker = FakeDocker(flagd(), ctr("valkey-cart"))
    faultctl.inject("scenario-01", docker, FLAG_SCENARIOS, state, sleep=lambda s: None)
    faultctl.inject("scenario-06", docker, FLAG_SCENARIOS, state, combo=True)
    log, problems = do_reset(docker, state)
    assert problems == []
    assert clean_flag_file.read() == FLAG_TEXT and clean_flag_file.restores == 1
    assert "restored demo.flagd.json from git" in log
    assert "restored scenario-06 on valkey-cart" in log
    assert not state.exists()


def test_reset_also_restores_a_manual_flag_ui_toggle(state, clean_flag_file):
    clean_flag_file.path.write_bytes(
        FLAG_TEXT.replace('"off"\n    },', '"on"\n    },').encode()
    )
    _log, problems = do_reset(FakeDocker(flagd()), state)
    assert clean_flag_file.read() == FLAG_TEXT and problems == []


def test_status_warns_when_flag_file_differs_from_head(state, clean_flag_file):
    docker = FakeDocker(flagd())
    assert faultctl.FLAG_FILE_WARNING not in faultctl.status(docker, state)
    clean_flag_file.path.write_bytes(FLAG_TEXT.replace("pay", "PAY").encode())
    assert faultctl.status(docker, state)[0] == faultctl.FLAG_FILE_WARNING


def test_second_scenario_needs_combo(state):
    docker = FakeDocker(ctr("valkey-cart"), ctr("email"))
    faultctl.inject("scenario-06", docker, SCENARIOS, state)
    with pytest.raises(faultctl.FaultctlError, match="--combo"):
        faultctl.inject("scenario-09", docker, SCENARIOS, state)


def test_shipped_flag_scenarios_use_keys_that_exist():
    scenarios = faultctl.load_scenarios()
    real = json.loads(
        (faultctl.REPO / faultctl.FLAG_FILE_REL).read_text(encoding="utf-8")
    )
    for sid, sc in scenarios.items():
        if sc["type"] == "flag":
            flag = real["flags"][sc["params"]["key"]]
            assert str(sc["params"]["variant"]) in flag["variants"], sid


def test_flag_edit_keeps_line_endings_byte_for_byte(state, tmp_path):
    crlf = FLAG_TEXT.replace("\n", "\r\n")
    (tmp_path / "crlf").mkdir()
    flags = FakeFlags(tmp_path / "crlf", text=crlf)
    flags.set_variant("payFail", "on")
    after = flags.path.read_bytes()
    assert (
        after
        == crlf.replace('"defaultVariant": "off"', '"defaultVariant": "on"', 1).encode()
    )
