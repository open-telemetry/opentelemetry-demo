"""Closed remediation loop: fresh approval per attempt, retry only on measured non-recovery, one final report."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import src.approval.pipeline as pipeline
from src.agent.agent import RETRY_INSTRUCTION, format_prior_attempts
from src.agent.report import validate_report
from src.agent.transcript import Transcript
from src.approval import loop
from src.approval.gate import HumanDecision
from src.approval.loop import clamp_attempts, configured_max_attempts, run_remediation_loop
from src.config import Settings
from src.events import EventLog
from src.remediation.backends import ActionBackend, ActionResult
from src.remediation.verifier import VerificationResult

ROOT = Path(__file__).resolve().parents[1]
INCIDENT = "INC-LOOP"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    monkeypatch.delenv("REMEDIATION_MAX_ATTEMPTS", raising=False)
    cfg = Settings(root_dir=tmp_path)
    cfg.audit_log_path = str(tmp_path / "audit.jsonl")
    cfg.report_output_dir = str(tmp_path / "out")
    cfg.kill_switch_file = str(tmp_path / ".kill_switch")
    cfg.kill_switch_enabled = False
    cfg.action_settle_seconds = 0
    return cfg


def report_path(cfg):
    return Path(cfg.report_output_dir) / INCIDENT / "report.json"


def diagnosed(category, service, alert="checkout errors"):
    t = Transcript(incident_id=INCIDENT, alert=alert)
    t.diagnosis = {"root_cause": {"service": service, "category": category, "summary": f"{category} on {service}"},
                   "impacted_services": ["checkout"], "severity": "HIGH"}
    t.gate = {"final_confidence": "high", "escalate": False}
    t.report = {"incident_id": INCIDENT, "timestamp": "2026-10-24T10:00:00+00:00", "status": "DIAGNOSED",
                "target_service": service, "impacted_services": ["checkout"], "severity": "HIGH",
                "root_cause_summary": "s", "root_cause_category": category, "confidence_score": 0.85,
                "evidence": {"trace_ids": ["4bf92f3577b34da6a3ce929d0e0e4736"], "metrics_summary": {}},
                "remediation": {"recommended_action": "x", "requires_approval": True, "dry_run": True}}
    return t


class ScriptedInvestigator:
    """Test double for agent.run: returns one prepared diagnosis per attempt, records the hints it got."""

    def __init__(self, cfg, *diagnoses, on_call=None):
        self.cfg, self.diagnoses, self.on_call = cfg, list(diagnoses), on_call
        self.calls = []

    def __call__(self, incident_id, prior_attempts):
        self.calls.append((incident_id, prior_attempts))
        if self.on_call:
            self.on_call(len(self.calls))
        return diagnosed(*self.diagnoses[len(self.calls) - 1])


class FakeTelemetry:
    """Test double for the verifier: scripted verification statuses, one per executed attempt."""

    def __init__(self, monkeypatch, *statuses, on_verify=None):
        self.statuses, self.on_verify = list(statuses), on_verify
        self.baselines, self.verified = [], []
        monkeypatch.setattr(pipeline, "capture_baseline", self.baseline)
        monkeypatch.setattr(pipeline, "verify_recovery", self.verify)

    def baseline(self, ctx, service, window_minutes=5):
        self.baselines.append(service)
        return {"service": service, "window_minutes": window_minutes, "error_rate": 0.3, "p95_ms": 900.0}

    def verify(self, ctx, action, baseline, settle_seconds, dry_run, sleep=None, events=None):
        if self.on_verify:
            self.on_verify(len(self.verified) + 1)
        status = "NOT_VERIFIED_DRY_RUN" if dry_run else self.statuses[len(self.verified)]
        self.verified.append(status)
        snap = baseline.get("snapshots", {}).get("checkout", baseline)
        after = dict(snap, error_rate=0.0 if status == "RECOVERED" else 0.3)
        return VerificationResult(status=status, recovered=status == "RECOVERED", before=snap, after=after,
                                  reasons=[f"scripted {status}"])


class FakeLiveBackend(ActionBackend):
    """Test double for a non-dry-run Action API backend: records calls, changes nothing."""
    name = "fake_live_test_double"
    dry_run = False

    def __init__(self, on_rollback=None):
        super().__init__()
        self.done, self.on_rollback = [], on_rollback

    def _perform(self, action, role):
        self.done.append((role, action.action_type.value, action.target_service))
        if role == "rollback" and self.on_rollback:
            self.on_rollback()
        return ActionResult("EXECUTED", action.action_id, action.action_type.value, action.target_service,
                            role, False, self.name, f"{role} done")


class CountingApprover:
    """Test double for the human: answers each approval request from a script and counts the requests."""

    def __init__(self, *answers, check=None):
        self.answers, self.check, self.requests = list(answers) or [True], check, []

    def __call__(self, action):
        self.requests.append(action.action_id)
        if self.check:
            self.check(action)
        ok = self.answers[min(len(self.requests), len(self.answers)) - 1]
        return HumanDecision(ok, "alice", "test", "2026-10-24T10:00:00Z", "ok" if ok else "no")


def run(cfg, investigate, approver, backend=None, max_attempts=3, dry_run=False):
    events = EventLog.from_settings(cfg, echo=False)
    return run_remediation_loop("checkout errors", settings=cfg, investigate=investigate, max_attempts=max_attempts,
                                approval_callback=approver, dry_run=dry_run, ctx=object(),
                                backend=backend if backend is not None else FakeLiveBackend(),
                                sleep=lambda s: None, events=events)


def audit(cfg):
    return [json.loads(x) for x in Path(cfg.audit_log_path).read_text().splitlines()]


def written_report(cfg):
    report = json.loads(report_path(cfg).read_text())
    ok, errors = validate_report(report)
    assert ok, errors
    return report


THROTTLE = ("traffic_spike", "frontend")
RESTART_CART = ("container_down_or_restarting", "cart")
RESTART_CHECKOUT = ("container_down_or_restarting", "checkout")


def test_recovers_on_attempt_1(settings, monkeypatch):
    FakeTelemetry(monkeypatch, "RECOVERED")
    inv, approver = ScriptedInvestigator(settings, THROTTLE), CountingApprover(True)
    out = run(settings, inv, approver)
    assert out.final_status == loop.RESOLVED_VERIFIED and out.status == pipeline.RECOVERED
    assert len(inv.calls) == 1 and len(approver.requests) == 1
    report = written_report(settings)
    assert report["status"] == "RESOLVED"
    assert report["remediation"]["final_status"] == "RESOLVED_VERIFIED"
    assert [a["outcome"] for a in report["remediation"]["attempts"]] == ["RECOVERED"]


def test_fails_then_recovers_on_attempt_2_with_two_approvals_and_one_report_written_last(settings, monkeypatch):
    telemetry = FakeTelemetry(monkeypatch, "NOT_RECOVERED", "RECOVERED")
    backend = FakeLiveBackend()
    inv, approver = ScriptedInvestigator(settings, THROTTLE, RESTART_CART), CountingApprover(True)
    out = run(settings, inv, approver, backend)

    assert out.final_status == loop.RESOLVED_VERIFIED and len(out.attempts) == 2
    assert approver.requests == [f"ACT-{INCIDENT}", f"ACT-{INCIDENT}-A2"]
    assert backend.done == [("action", "THROTTLE_LOAD_GENERATOR", "load-generator"),
                            ("rollback", "RESTORE_LOAD_GENERATOR", "load-generator"),
                            ("action", "RESTART_SERVICE", "cart")]
    assert telemetry.verified == ["NOT_RECOVERED", "RECOVERED"]

    hint = inv.calls[1][1]
    assert inv.calls[1][0] == INCIDENT and len(hint) == 1
    assert hint[0]["action_type"] == "THROTTLE_LOAD_GENERATOR" and hint[0]["verification"]["status"] == "NOT_RECOVERED"
    assert hint[0]["verification"]["before"]["error_rate"] == 0.3
    text = format_prior_attempts(hint)
    assert RETRY_INSTRUCTION in text and "not evidence" in text

    records = audit(settings)
    assert [r["event"] for r in records].count("REPORT_WRITTEN") == 1 and records[-1]["event"] == "REPORT_WRITTEN"
    attempt_2 = [r for r in records if r["data"].get("attempt") == 2]
    assert attempt_2 and all(r["summary"].startswith("attempt 2/3: ") for r in attempt_2)
    run_log = (Path(settings.report_output_dir) / INCIDENT / "run.log").read_text()
    assert "attempt 2/3: " in run_log
    assert (Path(settings.report_output_dir) / INCIDENT / "attempts" / "attempt-2.transcript.json").exists()

    report = written_report(settings)
    attempts = report["remediation"]["attempts"]
    assert [a["outcome"] for a in attempts] == ["NOT_RECOVERED_ROLLED_BACK", "RECOVERED"]
    assert attempts[0]["approval"]["approver"] == "alice" and attempts[0]["rollback_execution"]["role"] == "rollback"
    assert attempts[1]["verification"]["after"]["error_rate"] == 0.0
    assert report["status"] == "RESOLVED"


def test_exhausted_after_n_attempts_escalates(settings, monkeypatch):
    FakeTelemetry(monkeypatch, "NOT_RECOVERED", "NOT_RECOVERED", "NOT_RECOVERED")
    inv = ScriptedInvestigator(settings, THROTTLE, RESTART_CART, RESTART_CHECKOUT)
    approver = CountingApprover(True)
    out = run(settings, inv, approver, max_attempts=3)
    assert len(approver.requests) == 3 == len(out.attempts) == len(inv.calls)
    assert out.final_status == loop.UNRESOLVED_ESCALATED and "exhausted" in out.final_reason
    report = written_report(settings)
    assert report["status"] != "RESOLVED" and report["remediation"]["final_status"] == "UNRESOLVED_ESCALATED"
    assert [r["event"] for r in audit(settings)].count("ESCALATION") == 1


def test_n_attempts_means_n_fresh_approval_requests(settings, monkeypatch):
    FakeTelemetry(monkeypatch, "NOT_RECOVERED", "NOT_RECOVERED")
    approver = CountingApprover(True)
    out = run(settings, ScriptedInvestigator(settings, THROTTLE, RESTART_CART), approver, max_attempts=2)
    assert len(out.attempts) == 2 and len(approver.requests) == 2
    decisions = [r for r in audit(settings) if r["event"] == "APPROVAL_DECISION"]
    assert [d["data"]["attempt"] for d in decisions] == [1, 2]


def test_reject_on_attempt_2_stops_without_asking_again(settings, monkeypatch):
    FakeTelemetry(monkeypatch, "NOT_RECOVERED")
    inv = ScriptedInvestigator(settings, THROTTLE, RESTART_CART, RESTART_CHECKOUT)
    approver = CountingApprover(True, False)
    out = run(settings, inv, approver, max_attempts=3)
    assert out.final_status == pipeline.REJECTED and len(out.attempts) == 2
    assert len(approver.requests) == 2 and len(inv.calls) == 2
    assert written_report(settings)["remediation"]["final_status"] == "REJECTED"


def test_kill_switch_between_attempts_stops(settings, monkeypatch):
    FakeTelemetry(monkeypatch, "NOT_RECOVERED")
    sentinel = Path(settings.kill_switch_file)
    backend = FakeLiveBackend(on_rollback=sentinel.touch)
    inv = ScriptedInvestigator(settings, THROTTLE, RESTART_CART)
    out = run(settings, inv, CountingApprover(True), backend)
    assert out.final_status == pipeline.BLOCKED_BY_KILL_SWITCH
    assert len(inv.calls) == 1, "no re-investigation (and no LLM call) once the kill switch is engaged"
    checks = [r["data"] for r in audit(settings) if r["event"] == "KILL_SWITCH"]
    assert checks[-1]["checkpoint"] == "between_attempts" and checks[-1]["engaged"] is True
    assert written_report(settings)["remediation"]["final_status"] == "BLOCKED_BY_KILL_SWITCH"


def test_dry_run_does_one_pass(settings, monkeypatch):
    telemetry = FakeTelemetry(monkeypatch)
    inv, approver = ScriptedInvestigator(settings, THROTTLE, RESTART_CART), CountingApprover(True)
    events = EventLog.from_settings(settings, echo=False)
    out = run_remediation_loop("checkout errors", settings=settings, investigate=inv, max_attempts=3,
                               approval_callback=approver, dry_run=True, ctx=object(), events=events)
    assert out.final_status == loop.NOT_VERIFIED_DRY_RUN and out.status == pipeline.EXECUTED_DRY_RUN
    assert len(inv.calls) == 1 and len(approver.requests) == 1 and telemetry.verified == ["NOT_VERIFIED_DRY_RUN"]
    assert written_report(settings)["remediation"]["final_status"] == "NOT_VERIFIED_DRY_RUN"


def test_identical_repeat_is_refused_by_code_and_escalated(settings, monkeypatch):
    FakeTelemetry(monkeypatch, "NOT_RECOVERED")
    backend = FakeLiveBackend()
    approver = CountingApprover(True)
    out = run(settings, ScriptedInvestigator(settings, THROTTLE, ("traffic_spike", "checkout")), approver, backend)
    assert out.status == pipeline.REPEAT_REFUSED_ESCALATED and out.final_status == loop.UNRESOLVED_ESCALATED
    assert "already failed" in out.reason and "attempt 1" in out.reason
    assert len(approver.requests) == 1, "a refused repeat never reaches the human"
    assert [d[0] for d in backend.done] == ["action", "rollback"]


def test_no_report_on_disk_while_an_attempt_is_in_flight(settings, monkeypatch):
    seen = []

    def no_report(*_):
        seen.append(report_path(settings).exists())

    FakeTelemetry(monkeypatch, "NOT_RECOVERED", "RECOVERED", on_verify=no_report)
    inv = ScriptedInvestigator(settings, THROTTLE, RESTART_CART, on_call=no_report)
    approver = CountingApprover(True, check=no_report)
    run(settings, inv, approver, FakeLiveBackend(on_rollback=no_report))
    assert len(seen) == 7 and not any(seen)
    assert report_path(settings).exists()


def test_report_validates_against_schema_for_every_final_status(settings, monkeypatch):
    FakeTelemetry(monkeypatch, "NOT_RECOVERED")
    run(settings, ScriptedInvestigator(settings, THROTTLE, ("unknown", "cart")), CountingApprover(True))
    report = written_report(settings)
    assert report["remediation"]["final_status"] == "UNRESOLVED_ESCALATED"
    assert report["remediation"]["attempts"][1]["action"] is None


def test_attempts_are_capped_and_configurable(settings, monkeypatch):
    assert clamp_attempts(99) == loop.MAX_ATTEMPTS_CAP == 5
    assert clamp_attempts(0) == 1 and clamp_attempts("x") == loop.DEFAULT_MAX_ATTEMPTS == 3
    assert configured_max_attempts(settings) == 3
    monkeypatch.setenv("REMEDIATION_MAX_ATTEMPTS", "2")
    assert configured_max_attempts(settings) == 2


def test_verification_baselines_cover_the_alerted_service(settings, monkeypatch):
    telemetry = FakeTelemetry(monkeypatch, "RECOVERED")
    run(settings, ScriptedInvestigator(settings, RESTART_CART), CountingApprover(True))
    assert telemetry.baselines == ["cart", "checkout"]


# ---- no path can approve without a human ---------------------------------------------------------------

def _python_sources():
    return [p for d in ("src", "scripts") for p in (ROOT / d).rglob("*.py")]


def test_nothing_in_the_product_can_produce_a_bypassed_approval():
    allowed = {ROOT / "src" / "models" / "action.py", ROOT / "src" / "agent" / "report.py"}
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in _python_sources() if p not in allowed
            for n, line in enumerate(p.read_text().splitlines(), 1) if "BYPASSED" in line]
    assert hits == []
    report_lines = [l for l in (ROOT / "src" / "agent" / "report.py").read_text().splitlines() if "BYPASSED" in l]
    assert all("_APPROVAL_STATUSES" in l for l in report_lines)


def test_no_flag_env_var_or_cli_option_auto_approves():
    # Matches auto-approve style names: auto_approve, AUTO-APPROVE, skip_approval, no-approval, bypass_approval.
    pattern = re.compile(r"auto[_-]?approv|skip[_-]?approv|no[_-]approv|bypass[_-]?approv", re.IGNORECASE)
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in _python_sources()
            for n, line in enumerate(p.read_text().splitlines(), 1) if pattern.search(line)]
    assert hits == []
    assert Settings().require_human_approval is True


@pytest.mark.parametrize("flag", ["--auto-approve", "--yes", "--no-approval"])
def test_cli_rejects_auto_approve_options(flag, monkeypatch):
    import scripts.run_demo as demo
    import src.agent.__main__ as cli

    def no_llm():
        raise AssertionError("no LLM session may be created in tests")

    monkeypatch.setattr(cli, "session_factory", no_llm)
    monkeypatch.setattr(demo, "session_factory", no_llm)
    agent_main, demo_main = cli.main, demo.main

    for entry in (agent_main, demo_main):
        with pytest.raises(SystemExit):
            entry(["--alert", "x", flag])


def test_without_a_callback_the_real_prompt_rejects_when_there_is_no_tty(settings, monkeypatch):
    FakeTelemetry(monkeypatch, "NOT_RECOVERED")
    monkeypatch.setattr("sys.stdin", open("/dev/null"))
    inv = ScriptedInvestigator(settings, THROTTLE, RESTART_CART)
    out = run(settings, inv, None)
    assert out.final_status == pipeline.REJECTED and len(out.attempts) == 1 and len(inv.calls) == 1
