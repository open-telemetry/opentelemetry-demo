"""faultctl unit tests. Fake HTTP and Docker adapters only: no live demo is touched."""
import copy
import subprocess

import pytest

from dev.faultctl import flags
from dev.faultctl.__main__ import main
from dev.faultctl.catalog import ALLOWED_CONTAINERS, CATALOGUE
from dev.faultctl.docker_ops import DockerCli, DockerError, DockerTimeout
from dev.faultctl.outcome import Refused

PROJECT = "opentelemetry-demo"


def make_flag_set():
    def graded():
        return {"defaultVariant": "off", "state": "ENABLED",
                "variants": {"off": 0, "50%": 0.5, "100%": 1}}

    def boolean():
        return {"defaultVariant": "off", "state": "ENABLED", "variants": {"off": False, "on": True}}

    targeted = boolean()
    targeted["targeting"] = {"if": [{"==": [{"var": "product_id"}, "X1"]}, "off", "off"]}
    return {"flags": {
        "paymentFailure": graded(), "cartFailure": graded(), "adFailure": boolean(),
        "productCatalogFailure": targeted, "productCatalogLockContention": boolean(),
        "adHighCpu": boolean(), "someOtherFlag": boolean(),
    }}


class FakeHttp:
    def __init__(self, flag_set=None):
        self.state = flag_set or make_flag_set()
        self.reads = 0
        self.writes = []
        self.write_error = None  # exception to raise from post_json
        self.on_write = None  # callable(state) run after a successful write, to simulate drift
        self.fail_reads_after_write = False
        self.status_codes = {}

    def get_json(self, path):
        assert path == flags.READ_PATH
        if self.fail_reads_after_write and self.writes:
            raise flags.HttpFailure("boom")
        self.reads += 1
        return copy.deepcopy(self.state)

    def post_json(self, path, body):
        assert path == flags.WRITE_PATH
        self.writes.append(copy.deepcopy(body))
        if self.write_error:
            raise self.write_error
        self.state = copy.deepcopy(body["data"])
        if self.on_write:
            self.on_write(self.state)

    def get_status(self, path):
        return self.status_codes.get(path, 200)


def container_info(name, running=True, health="healthy", project=PROJECT):
    info = {"Name": "/" + name, "RestartCount": 0, "Config": {"Labels": {"com.docker.compose.project": project}},
            "State": {"Running": running, "Status": "running" if running else "exited"}}
    if health:
        info["State"]["Health"] = {"Status": health}
    return info


class FakeDocker:
    def __init__(self, names=None, host="unix:///var/run/docker.sock"):
        self.containers = {n: container_info(n) for n in (names or ALLOWED_CONTAINERS)}
        self.host = host
        self.calls = []
        self.stop_error = None
        self.start_stays_down = False
        self.health_after_start = "healthy"

    def daemon_host(self):
        return self.host

    def inspect(self, name):
        self.calls.append(("inspect", name))
        return copy.deepcopy(self.containers.get(name))

    def stop(self, name):
        self.calls.append(("stop", name))
        if self.stop_error:
            raise self.stop_error
        self.containers[name] = container_info(name, running=False, health=None)

    def start(self, name):
        self.calls.append(("start", name))
        if not self.start_stays_down:
            self.containers[name] = container_info(name, running=True, health=self.health_after_start)

    def project_containers(self, project):
        return [copy.deepcopy(c) for c in self.containers.values()]

    def changes(self):
        return [c for c in self.calls if c[0] in ("stop", "start")]


@pytest.fixture
def env(tmp_path):
    return {"http": FakeHttp(), "docker": FakeDocker(), "gt": tmp_path / "ground_truth.md"}


def run(env, *argv):
    return main(list(argv), http=env["http"], docker=env["docker"], ground_truth_path=env["gt"],
                sleep=lambda s: None, confirm=env.get("confirm", lambda p: "no"))


def rows(env):
    lines = env["gt"].read_text().splitlines()
    return [[c.strip() for c in line.strip("|").split("|")] for line in lines if line.startswith("| 20")]


# --- allowlist and rejection ---

def test_catalogue_is_exactly_the_agreed_allowlist():
    assert set(CATALOGUE) == {
        "cache-unavailable", "database-unavailable", "currency-down", "payment-failure", "cart-failure",
        "ad-failure", "product-catalog-failure", "product-catalog-lock-contention", "ad-high-cpu"}
    assert ALLOWED_CONTAINERS == {"valkey-cart", "astronomy-db", "currency"}


def test_unknown_incident_rejected_and_nothing_touched(env):
    assert run(env, "inject", "emit-raw-pii") == 2
    assert run(env, "reset", "not-a-thing") == 2
    assert env["http"].writes == [] and env["http"].reads == 0
    assert env["docker"].calls == []
    assert [r[6] for r in rows(env)] == ["refused", "refused"]


def test_unknown_variant_rejected_without_write(env):
    assert run(env, "inject", "payment-failure", "--variant", "200%") == 2
    assert env["http"].writes == []
    assert rows(env)[0][6] == "refused"


def test_resting_variant_rejected_for_inject(env):
    assert run(env, "inject", "payment-failure", "--variant", "off") == 2
    assert env["http"].writes == []


def test_variant_on_container_incident_rejected(env):
    assert run(env, "inject", "cache-unavailable", "--variant", "on") == 2
    assert env["docker"].changes() == []


def test_disabled_flag_refused(env):
    env["http"].state["flags"]["adFailure"]["state"] = "DISABLED"
    assert run(env, "inject", "ad-failure") == 2
    assert env["http"].writes == []


# --- dry run ---

@pytest.mark.parametrize("incident", ["payment-failure", "cache-unavailable"])
def test_dry_run_changes_nothing_but_is_logged(env, incident):
    before = copy.deepcopy(env["http"].state)
    assert run(env, "inject", incident, "--dry-run") == 0
    assert env["http"].writes == [] and env["docker"].changes() == []
    assert env["http"].state == before
    assert [r[1:3] + [r[6]] for r in rows(env)] == [["inject", incident, "dry-run"]]


def test_dry_run_reset_of_active_incident_plans_without_acting(env):
    run(env, "inject", "cache-unavailable")
    assert run(env, "reset", "cache-unavailable", "--dry-run") == 0
    assert [c[0] for c in env["docker"].changes()] == ["stop"]
    assert not env["docker"].containers["valkey-cart"]["State"]["Running"]


# --- flag faults ---

def test_flag_inject_and_reset_verified_and_only_target_flag_written(env):
    original = copy.deepcopy(env["http"].state)
    assert run(env, "inject", "payment-failure") == 0
    sent = env["http"].writes[0]["data"]
    expected = copy.deepcopy(original)
    expected["flags"]["paymentFailure"]["defaultVariant"] = "50%"
    assert sent == expected  # every other flag is byte-for-byte what was read
    assert run(env, "reset", "payment-failure") == 0
    assert env["http"].state == original


def test_explicit_variant_is_used(env):
    assert run(env, "inject", "cart-failure", "--variant", "100%") == 0
    assert env["http"].state["flags"]["cartFailure"]["defaultVariant"] == "100%"


def test_targeted_flag_changes_the_rule_not_the_default(env):
    assert run(env, "inject", "product-catalog-failure") == 0
    flag = env["http"].state["flags"]["productCatalogFailure"]
    assert flag["targeting"]["if"][1:] == ["on", "off"]
    assert flag["defaultVariant"] == "off"
    assert run(env, "reset", "product-catalog-failure") == 0
    assert env["http"].state["flags"]["productCatalogFailure"]["targeting"]["if"][1:] == ["off", "off"]


def test_unsupported_targeting_shape_refused(env):
    env["http"].state["flags"]["productCatalogFailure"]["targeting"] = {"fractional": [["on", 1]]}
    assert run(env, "inject", "product-catalog-failure") == 2
    assert env["http"].writes == []


def test_flag_reset_is_idempotent(env):
    assert run(env, "reset", "ad-failure") == 0  # already resting
    assert env["http"].writes == []
    run(env, "inject", "ad-failure")
    assert run(env, "reset", "ad-failure") == 0
    writes = len(env["http"].writes)
    assert run(env, "reset", "ad-failure") == 0
    assert len(env["http"].writes) == writes


def test_flag_inject_is_idempotent(env):
    run(env, "inject", "ad-failure")
    writes = len(env["http"].writes)
    assert run(env, "inject", "ad-failure") == 0
    assert len(env["http"].writes) == writes


def test_missing_flag_fails(env):
    del env["http"].state["flags"]["adHighCpu"]
    assert run(env, "inject", "ad-high-cpu") == 4


def test_write_timeout_is_timed_out_and_not_retried(env):
    env["http"].write_error = flags.HttpTimeout("slow")
    assert run(env, "inject", "ad-failure") == 5
    assert len(env["http"].writes) == 1
    assert rows(env)[0][6] == "timed-out"


def test_write_failure_is_failed(env):
    env["http"].write_error = flags.HttpFailure("HTTP 500")
    assert run(env, "inject", "ad-failure") == 4


def test_read_failure_before_write_is_failed_and_changes_nothing(env):
    def boom(path):
        raise flags.HttpFailure("down")
    env["http"].get_json = boom
    assert run(env, "inject", "ad-failure") == 4
    assert env["http"].writes == []


def test_reread_failure_is_applied_but_unverified(env):
    env["http"].fail_reads_after_write = True
    assert run(env, "inject", "ad-failure") == 3
    assert rows(env)[0][6] == "applied-unverified"


def test_another_flag_changing_during_write_is_unverified(env):
    def drift(state):
        state["flags"]["someOtherFlag"]["defaultVariant"] = "on"
    env["http"].on_write = drift
    assert run(env, "inject", "ad-failure") == 3


def test_target_not_as_written_is_failed(env):
    def revert(state):
        state["flags"]["adFailure"]["defaultVariant"] = "off"
    env["http"].on_write = revert
    assert run(env, "inject", "ad-failure") == 4


# --- container faults ---

def test_container_inject_and_reset_verified(env):
    assert run(env, "inject", "cache-unavailable") == 0
    assert not env["docker"].containers["valkey-cart"]["State"]["Running"]
    assert run(env, "reset", "cache-unavailable") == 0
    assert env["docker"].containers["valkey-cart"]["State"]["Running"]
    assert env["docker"].changes() == [("stop", "valkey-cart"), ("start", "valkey-cart")]


def test_container_reset_idempotent_and_inject_idempotent(env):
    assert run(env, "reset", "currency-down") == 0  # already running
    assert env["docker"].changes() == []
    run(env, "inject", "currency-down")
    assert run(env, "inject", "currency-down") == 0  # already stopped
    assert env["docker"].changes() == [("stop", "currency")]


def test_container_in_other_compose_project_refused(env):
    env["docker"].containers["valkey-cart"] = container_info("valkey-cart", project="someone-else")
    assert run(env, "inject", "cache-unavailable") == 2
    assert env["docker"].changes() == []


def test_remote_docker_daemon_refused(env):
    env["docker"].host = "ssh://user@prod-box"
    assert run(env, "inject", "cache-unavailable") == 2
    assert env["docker"].calls == []


def test_missing_container_is_failed(env):
    del env["docker"].containers["astronomy-db"]
    assert run(env, "inject", "database-unavailable") == 4


def test_stop_timeout_is_timed_out_and_not_retried(env):
    env["docker"].stop_error = DockerTimeout("docker stop timed out")
    assert run(env, "inject", "cache-unavailable") == 5
    assert env["docker"].changes() == [("stop", "valkey-cart")]


def test_start_that_never_becomes_healthy_is_unverified(env):
    run(env, "inject", "cache-unavailable")
    env["docker"].health_after_start = "starting"
    assert run(env, "reset", "cache-unavailable") == 3


def test_start_that_does_not_run_is_failed(env):
    run(env, "inject", "cache-unavailable")
    env["docker"].start_stays_down = True
    assert run(env, "reset", "cache-unavailable") == 4


# --- DockerCli: the adapter itself enforces the allowlist ---

class RecordingRunner:
    def __init__(self):
        self.commands = []

    def __call__(self, cmd, **kwargs):
        self.commands.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")


@pytest.mark.parametrize("name", ["frontend", "valkey-cart; rm -rf /", "", "grafana", "$(id)"])
def test_non_allowlisted_container_refused_before_any_command(name):
    runner = RecordingRunner()
    cli = DockerCli(runner)
    for method in (cli.inspect, cli.stop, cli.start):
        with pytest.raises(Refused):
            method(name)
    assert runner.commands == []


def test_docker_commands_are_fixed_lists_without_shell():
    runner = RecordingRunner()
    cli = DockerCli(runner)
    cli.stop("valkey-cart")
    cli.start("valkey-cart")
    assert [c for c, _ in runner.commands] == [["docker", "stop", "valkey-cart"], ["docker", "start", "valkey-cart"]]
    assert all(not kw.get("shell") for _, kw in runner.commands)


def test_docker_timeout_and_missing_cli_are_translated():
    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    def absent(cmd, **kw):
        raise FileNotFoundError("docker")
    with pytest.raises(DockerTimeout):
        DockerCli(slow).stop("currency")
    with pytest.raises(DockerError):
        DockerCli(absent).stop("currency")


# --- loopback only ---

@pytest.mark.parametrize("url", ["http://example.com:8080", "http://10.0.0.5:8080", "http://localhost.evil.com",
                                 "http://127.0.0.1@evil.com/", "ftp://localhost", "localhost:8080"])
def test_non_loopback_base_url_refused(env, url):
    code = main(["--base-url", url, "inject", "payment-failure"], docker=env["docker"],
                ground_truth_path=env["gt"], sleep=lambda s: None)
    assert code == 2
    assert env["docker"].calls == []
    assert rows(env)[0][6] == "refused"


@pytest.mark.parametrize("url", ["http://localhost:8080", "http://127.0.0.1:8080/", "http://[::1]:8080"])
def test_loopback_base_urls_accepted(url):
    assert flags.require_loopback(url) == url.rstrip("/")


# --- ground truth ---

def test_ground_truth_row_for_every_operation(env):
    run(env, "inject", "payment-failure")
    run(env, "reset", "payment-failure")
    run(env, "inject", "cache-unavailable", "--dry-run")
    run(env, "inject", "nope")
    env["http"].write_error = flags.HttpFailure("x")
    run(env, "inject", "ad-failure")
    got = rows(env)
    assert [(r[1], r[2], r[6]) for r in got] == [
        ("inject", "payment-failure", "verified"), ("reset", "payment-failure", "verified"),
        ("inject", "cache-unavailable", "dry-run"), ("inject", "nope", "refused"),
        ("inject", "ad-failure", "failed")]
    time, action, incident, mechanism, target, variant, outcome, _ = got[0]
    assert (mechanism, target, variant) == ("flag", "paymentFailure", "50%")
    assert time[-6] in "+-" and "T" in time  # ISO timestamp with a UTC offset
    assert (got[1][5], got[2][3], got[2][4], got[2][5]) == ("off", "container", "valkey-cart", "-")


def test_ground_truth_is_append_only_and_header_written_once(env):
    env["gt"].write_text("# existing notes\n")
    run(env, "inject", "ad-failure")
    run(env, "reset", "ad-failure")
    text = env["gt"].read_text()
    assert text.startswith("# existing notes\n")
    assert "| time | action |" not in text  # a non-empty file is never given a second header
    assert len(rows(env)) == 2


def test_ground_truth_created_with_header_when_missing(env):
    assert not env["gt"].exists()
    run(env, "inject", "ad-failure")
    text = env["gt"].read_text()
    assert text.startswith("# Ground truth") and "| time | action |" in text


def test_unwritable_ground_truth_fails_loudly(env, tmp_path):
    env["gt"] = tmp_path  # a directory: opening it for append raises OSError
    assert run(env, "inject", "ad-failure") == 4


# --- reset-all, list, status ---

def test_reset_all_declined_changes_nothing(env):
    run(env, "inject", "cache-unavailable")
    run(env, "inject", "payment-failure")
    n_calls, n_writes = len(env["docker"].changes()), len(env["http"].writes)
    env["confirm"] = lambda prompt: "no"
    assert run(env, "reset-all") == 2
    assert (len(env["docker"].changes()), len(env["http"].writes)) == (n_calls, n_writes)


def test_reset_all_yes_resets_everything(env):
    original = copy.deepcopy(env["http"].state)
    run(env, "inject", "cache-unavailable")
    run(env, "inject", "payment-failure")
    run(env, "inject", "product-catalog-failure")
    assert run(env, "reset-all", "--yes") == 0
    assert env["http"].state == original
    assert all(c["State"]["Running"] for c in env["docker"].containers.values())
    assert len([r for r in rows(env) if r[1] == "reset"]) == len(CATALOGUE)


def test_reset_all_confirmation_accepted(env):
    run(env, "inject", "ad-failure")
    env["confirm"] = lambda prompt: "yes"
    assert run(env, "reset-all") == 0
    assert env["http"].state["flags"]["adFailure"]["defaultVariant"] == "off"


def test_reset_all_dry_run_needs_no_confirmation_and_changes_nothing(env):
    run(env, "inject", "ad-failure")
    writes = len(env["http"].writes)
    assert run(env, "reset-all", "--dry-run") == 0
    assert len(env["http"].writes) == writes


def test_list_shows_exactly_the_allowlist(env, capsys):
    assert run(env, "list") == 0
    listed = [line.split()[0] for line in capsys.readouterr().out.splitlines()[1:]]
    assert listed == list(CATALOGUE)


def test_status_reports_health_but_never_flag_state(env, capsys):
    run(env, "inject", "payment-failure")
    run(env, "inject", "cache-unavailable")
    capsys.readouterr()
    code = run(env, "status")
    out = capsys.readouterr().out
    assert code == 1  # valkey-cart is down
    assert "valkey-cart" in out and "exited" in out
    assert "paymentFailure" not in out and "50%" not in out


def test_status_healthy_exit_zero(env, capsys):
    assert run(env, "status") == 0
