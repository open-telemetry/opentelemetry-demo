"""Alert watcher: rules, debounce, one run at a time, re-arm after recovery, daily cap, symptom-only alert text."""
from src.alerting.watcher import AlertWatcher, Rules, evaluate

HEALTHY = {"checkout": {"error_rate_ratio": 0.0, "p95_latency_ms": 300, "requests_per_second": 0.5},
           "frontend": {"error_rate_ratio": 0.0, "p95_latency_ms": 900, "requests_per_second": 12.0}}
BROKEN = {"checkout": {"error_rate_ratio": 0.6, "p95_latency_ms": 9000, "requests_per_second": 0.5},
          "frontend": {"error_rate_ratio": 0.08, "p95_latency_ms": 900, "requests_per_second": 12.0},
          "payment": {"error_rate_ratio": 0.0, "p95_latency_ms": 5, "requests_per_second": 0.0}}


class Fake:
    def __init__(self, metrics):
        self.metrics, self.launched, self.busy, self.now, self.lines = metrics, [], False, 1_000_000.0, []

    def watcher(self, **rules):
        return AlertWatcher(lambda: self.metrics, self.launched.append, lambda: self.busy,
                            rules=Rules(**rules), clock=lambda: self.now, log=self.lines.append)


def test_evaluate_names_the_symptom_worst_first():
    alerts = evaluate(BROKEN, Rules())
    assert [a.service for a in alerts] == ["checkout", "frontend"]
    assert alerts[0].text == "Error rate above 5% on checkout"
    assert all("payment" not in a.text for a in alerts)


def test_low_traffic_needs_enough_failures():
    one_failure = {"checkout": {"error_rate_ratio": 0.08, "p95_latency_ms": 300, "requests_per_second": 0.04}}
    assert evaluate(one_failure, Rules()) == []
    assert evaluate(one_failure, Rules(min_errors=0.5)) != []


def test_latency_rule_and_disabling_it():
    slow = {"ad": {"error_rate_ratio": 0.0, "p95_latency_ms": 8000, "requests_per_second": 1.0}}
    assert evaluate(slow, Rules())[0].text == "p95 latency above 5000 ms on ad"
    assert evaluate(slow, Rules(p95_ms=0)) == []


def test_fires_after_consecutive_checks_once_per_incident():
    f = Fake(BROKEN)
    w = f.watcher()
    assert w.poll() is None
    alert = w.poll()
    assert alert.service == "checkout" and f.launched == [alert]
    f.now += 30
    assert w.poll() is None and len(f.launched) == 1


def test_no_second_run_while_one_is_running():
    f = Fake(HEALTHY)
    w = f.watcher(consecutive=1)
    f.busy = True
    f.metrics = BROKEN
    assert w.poll() is None and f.launched == []
    f.busy = False
    f.now += 30
    assert w.poll() is None and f.launched == []


def test_rearms_after_recovery():
    f = Fake(BROKEN)
    w = f.watcher(consecutive=1)
    assert w.poll() is not None
    f.metrics, f.now = HEALTHY, f.now + 30
    assert w.poll() is None
    assert "resolved: checkout" in f.lines
    f.metrics, f.now = BROKEN, f.now + 30
    assert w.poll() is not None and len(f.launched) == 2


def test_refires_after_refire_period_if_still_broken():
    f = Fake(BROKEN)
    w = f.watcher(consecutive=1, refire_seconds=600)
    assert w.poll() is not None
    f.now += 599
    assert w.poll() is None
    f.now += 2
    assert w.poll() is not None


def test_daily_cap_and_reset_next_day():
    f = Fake(BROKEN)
    w = f.watcher(consecutive=1, refire_seconds=0, max_runs_per_day=2)
    assert w.poll() and w.poll()
    assert w.poll() is None and len(f.launched) == 2
    assert any("daily cap" in line for line in f.lines)
    f.now += 86_400
    assert w.poll() is not None


def test_metrics_error_is_logged_not_raised():
    def boom():
        raise ConnectionError("prometheus down")

    lines = []
    w = AlertWatcher(boom, lambda a: None, lambda: False, log=lines.append)
    assert w.poll() is None and "prometheus down" in lines[0]


def test_launcher_starts_agent_with_human_chat_approval_in_dry_run(tmp_path, monkeypatch):
    import subprocess

    from src.alerting.watcher import Alert, AgentLauncher

    calls = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            calls.append((cmd, kwargs))

        def poll(self):
            return None

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    notes = []
    launcher = AgentLauncher(tmp_path, tmp_path / "logs", approval_timeout=900, notify=notes.append)
    launcher(Alert("checkout", "Error rate above 5% on checkout", 1.6))
    cmd, kwargs = calls[0]
    assert cmd[1:] == ["-m", "src.agent", "--alert", "Error rate above 5% on checkout",
                       "--approve-via", "chat", "--dry-run"]
    assert kwargs["env"]["APPROVAL_TIMEOUT_SECONDS"] == "900"
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert launcher.running() and notes == ["Error rate above 5% on checkout"]
    assert len(list((tmp_path / "logs").glob("auto-*-checkout.log"))) == 1
