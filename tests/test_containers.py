import json
import subprocess

from tools.containers import container_health, parse_inspect

# Trimmed from real `docker inspect` output: one healthy container, one exited, one without a health check,
# one belonging to the flag backend (must be filtered out).
def inspect_entry(name, service, status, health=None, exit_code=0, restarts=0, oom=False, started="2026-10-23T17:25:19Z"):
    state = {"Status": status, "ExitCode": exit_code, "OOMKilled": oom, "StartedAt": started, "FinishedAt": "2026-10-23T17:40:00Z"}
    if health:
        state["Health"] = {"Status": health, "Log": [{"Output": "PONG"}]}
    return {"Name": f"/{name}", "RestartCount": restarts, "State": state,
            "Config": {"Labels": {"com.docker.compose.service": service, "com.docker.compose.project": "opentelemetry-demo"}}}


INSPECT = [
    inspect_entry("cart", "cart", "running"),
    inspect_entry("valkey-cart", "valkey-cart", "exited", exit_code=137),
    inspect_entry("payment", "payment", "running", health="healthy"),
    inspect_entry("flagd", "flagd", "running"),
    inspect_entry("flagd-ui", "flagd-ui", "running", health="healthy"),
]
STATS = [
    {"Name": "cart", "CPUPerc": "0.78%", "MemPerc": "49.91%"},
    {"Name": "payment", "CPUPerc": "1.50%", "MemPerc": "72.00%"},
]


class FakeDocker:
    def __init__(self, inspect=INSPECT, ids="aaa\nbbb\nccc\nddd\neee\n", stats=STATS, fail=None, stats_fail=False):
        self.inspect, self.ids, self.stats, self.fail, self.stats_fail, self.calls = inspect, ids, stats, fail, stats_fail, []

    def __call__(self, args, capture_output, text, timeout):
        self.calls.append(args)
        assert args[0] == "docker" and isinstance(args, list)
        verb = args[1]
        if self.fail == "missing":
            raise FileNotFoundError("docker")
        if self.fail == "timeout":
            raise subprocess.TimeoutExpired(args, timeout)
        if self.fail == "daemon":
            return subprocess.CompletedProcess(args, 1, "", "Cannot connect to the Docker daemon")
        if verb == "ps":
            return subprocess.CompletedProcess(args, 0, self.ids, "")
        if verb == "inspect":
            return subprocess.CompletedProcess(args, 0, json.dumps(self.inspect), "")
        if verb == "stats":
            if self.stats_fail:
                raise subprocess.TimeoutExpired(args, timeout)
            return subprocess.CompletedProcess(args, 0, "\n".join(json.dumps(s) for s in self.stats), "")
        raise AssertionError(f"unexpected docker call {args}")


def test_parse_inspect_extracts_every_required_field():
    rows = {r["name"]: r for r in parse_inspect(json.dumps(INSPECT))}
    valkey = rows["valkey-cart"]
    assert valkey == {
        "name": "valkey-cart", "compose_service": "valkey-cart", "status": "exited", "health": "none",
        "restart_count": 0, "exit_code": 137, "oom_killed": False,
        "started_at": "2026-10-23T17:25:19Z", "finished_at": "2026-10-23T17:40:00Z",
    }
    assert rows["payment"]["health"] == "healthy"


def test_exited_container_is_listed_first_and_summarised():
    result = container_health(project="opentelemetry-demo", runner=FakeDocker())
    assert result.state == "data"
    assert result.items[0]["name"] == "valkey-cart" and result.items[0]["status"] == "exited"
    assert result.extra["summary"]["not_running"] == ["valkey-cart"]
    assert result.extra["summary"]["running"] == 2 and result.extra["summary"]["total"] == 3


def test_flag_containers_are_filtered_out():
    result = container_health(project="opentelemetry-demo", runner=FakeDocker())
    assert {r["name"] for r in result.items} == {"cart", "valkey-cart", "payment"}
    assert "flagd" not in json.dumps(result.to_dict())


def test_stats_are_added_to_running_containers_only():
    rows = {r["name"]: r for r in container_health(project="opentelemetry-demo", runner=FakeDocker()).items}
    assert rows["cart"]["cpu_percent"] == 0.78 and rows["payment"]["memory_percent"] == 72.0
    assert "cpu_percent" not in rows["valkey-cart"]


def test_slow_stats_do_not_lose_the_rest():
    result = container_health(project="opentelemetry-demo", runner=FakeDocker(stats_fail=True))
    assert result.state == "data" and len(result.items) == 3
    assert any("cpu/memory unavailable" in n for n in result.notes)


def test_commands_are_fixed_argument_lists_with_the_project_filter():
    fake = FakeDocker()
    container_health(project="opentelemetry-demo", runner=fake)
    assert fake.calls[0] == ["docker", "ps", "-a", "-q", "--filter", "label=com.docker.compose.project=opentelemetry-demo"]


def test_backend_error_when_docker_is_unusable():
    for failure in ("missing", "timeout", "daemon"):
        result = container_health(project="opentelemetry-demo", runner=FakeDocker(fail=failure))
        assert result.state == "backend_error" and result.error and result.items == [], failure


def test_no_data_when_project_has_no_containers():
    result = container_health(project="opentelemetry-demo", runner=FakeDocker(ids=""))
    assert result.state == "no_data" and result.items == []


def test_bad_project_name_is_rejected_without_calling_docker():
    fake = FakeDocker()
    result = container_health(project="x; rm -rf /", runner=fake)
    assert result.state == "backend_error" and fake.calls == []
