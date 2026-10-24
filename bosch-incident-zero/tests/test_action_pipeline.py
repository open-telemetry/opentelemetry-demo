"""Safety pipeline: approval, kill switch checkpoints, dry run, verification outcomes and events."""
from __future__ import annotations

import json
import socket
import sys
import types
from pathlib import Path

import pytest

import src.approval.pipeline as pipeline
from src.agent.transcript import Transcript
from src.approval.gate import HumanDecision
from src.approval.pipeline import execute_safety_pipeline
from src.config import Settings
from src.events import EventLog
from src.remediation.backends import ActionBackend, ActionResult
from src.remediation.kill_switch import KillSwitch
from src.remediation.verifier import VerificationResult


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    cfg = Settings(root_dir=tmp_path)
    cfg.audit_log_path = str(tmp_path / "audit.jsonl")
    cfg.report_output_dir = str(tmp_path / "out")
    cfg.kill_switch_file = str(tmp_path / ".kill_switch")
    cfg.kill_switch_enabled = False
    cfg.dry_run_mode = True
    cfg.action_settle_seconds = 0
    return cfg


@pytest.fixture
def verifier(monkeypatch):
    calls = {"baseline": [], "verify": [], "status": "NOT_VERIFIED_DRY_RUN"}

    def baseline(ctx, service, window_minutes=5):
        calls["baseline"].append(service)
        return {"service": service, "window_minutes": window_minutes}

    def verify(ctx, action, baseline, settle_seconds, dry_run, sleep=None, events=None):
        calls["verify"].append(dry_run)
        status = "NOT_VERIFIED_DRY_RUN" if dry_run else calls["status"]
        return VerificationResult(status=status, recovered=status == "RECOVERED", before=baseline)

    monkeypatch.setattr(pipeline, "capture_baseline", baseline)
    monkeypatch.setattr(pipeline, "verify_recovery", verify)
    return calls


def incident(category="traffic_spike", service="frontend", escalate=False):
    t = Transcript(incident_id="INC-PIPE", alert="frontend flooded")
    t.diagnosis = {"root_cause": {"service": service, "category": category, "summary": "s"}}
    t.gate = {"final_confidence": "high", "escalate": escalate}
    t.report = {"incident_id": "INC-PIPE", "target_service": service, "root_cause_category": category,
                "remediation": {"recommended_action": "x", "requires_approval": True, "dry_run": True}}
    return t


def approve(action):
    return HumanDecision(True, "alice", "test", "2026-10-24T00:00:00Z", "ok")


def run(settings, t=None, **kw):
    kw.setdefault("ctx", object())
    kw.setdefault("events", EventLog.from_settings(settings, echo=False))
    return execute_safety_pipeline(t or incident(), settings=settings, **kw)


def names(outcome):
    return [r["event"] for r in outcome.timeline]


class LiveBackend(ActionBackend):
    name = "fake_live"
    dry_run = False

    def __init__(self):
        super().__init__()
        self.done = []

    def _perform(self, action, role):
        self.done.append((role, action.action_id))
        return ActionResult("EXECUTED", action.action_id, action.action_type.value, action.target_service,
                            role, False, self.name, f"{role} done")


def test_dry_run_happy_path_events_in_order_and_no_network(settings, verifier, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    outcome = run(settings, approval_callback=approve)

    assert outcome.status == pipeline.EXECUTED_DRY_RUN
    assert outcome.action.approver == "alice" and outcome.action.executed_at
    assert outcome.action.recovery_verified is False
    assert verifier["baseline"] == ["frontend"] and verifier["verify"] == [True]
    assert names(outcome) == ["PLAN", "KILL_SWITCH", "APPROVAL_REQUESTED", "APPROVAL_DECISION",
                              "KILL_SWITCH", "KILL_SWITCH", "DRY_RUN"]
    checkpoints = [r["data"]["checkpoint"] for r in outcome.timeline if r["event"] == "KILL_SWITCH"]
    assert checkpoints == ["plan", "post_approval", "pre_execute"]
    lines = [json.loads(x) for x in Path(settings.audit_log_path).read_text().splitlines()]
    assert all(rec["ts"] and rec["incident_id"] == "INC-PIPE" for rec in lines)
    assert lines[-1]["event"] == "REPORT_WRITTEN"
    report = json.loads((Path(settings.report_output_dir) / "INC-PIPE" / "report.json").read_text())
    assert report["remediation"]["pipeline_status"] == "EXECUTED_DRY_RUN"
    assert (Path(settings.report_output_dir) / "INC-PIPE" / "run.log").exists()


def test_reject_and_default_reject(settings, verifier):
    no = run(settings, approval_callback=lambda a: HumanDecision(False, "bob", "test", "t", "no"))
    assert no.status == pipeline.REJECTED and no.action.executed_at is None
    assert names(no)[-1] == "ESCALATION"
    assert verifier["verify"] == []


def test_approval_timeout_rejects(settings, verifier):
    def timeout(action):
        raise TimeoutError

    assert run(settings, approval_callback=timeout).status == pipeline.REJECTED


def test_no_action_when_gate_escalated(settings, verifier):
    asked = []
    outcome = run(settings, incident(escalate=True), approval_callback=lambda a: asked.append(a) or True)
    assert outcome.status == pipeline.NO_ACTION_ESCALATED and outcome.action is None
    assert asked == [] and verifier["baseline"] == []
    assert outcome.timeline[0]["summary"].startswith("no action: escalated")


def test_reversible_action_without_rollback_is_not_executed(settings, verifier, monkeypatch):
    from src.models.action import ActionType, RemediationAction
    from src.remediation.planner import PlanDecision
    bare = RemediationAction(action_id="ACT-X", action_type=ActionType.THROTTLE_LOAD_GENERATOR,
                             target_service="load-generator", description="throttle")
    monkeypatch.setattr(pipeline, "plan_with_reason", lambda t, platform: PlanDecision(bare, "test"))
    asked = []
    outcome = run(settings, approval_callback=lambda a: asked.append(a) or True)
    assert outcome.status == pipeline.NO_ACTION_ESCALATED
    assert "no approved rollback" in outcome.reason and asked == []


RESTART = ("container_down_or_restarting", "cart")


def test_irreversible_restart_approved_in_dry_run(settings, verifier):
    seen = []
    outcome = run(settings, incident(*RESTART), approval_callback=lambda a: seen.append(a) or approve(a))
    assert seen[0].irreversible is True and seen[0].rollback is None
    assert outcome.status == pipeline.EXECUTED_DRY_RUN
    assert outcome.approval.irreversible_acknowledged is True
    requested = [r for r in outcome.timeline if r["event"] == "APPROVAL_REQUESTED"][0]["data"]
    decided = [r for r in outcome.timeline if r["event"] == "APPROVAL_DECISION"][0]["data"]
    assert requested["irreversible"] is True and decided["irreversible_acknowledged"] is True


def test_irreversible_restart_rejected(settings, verifier):
    outcome = run(settings, incident(*RESTART),
                  approval_callback=lambda a: HumanDecision(False, "bob", "test", "t", "no"))
    assert outcome.status == pipeline.REJECTED and outcome.action.executed_at is None


def test_irreversible_restart_blocked_by_kill_switch_after_approval(settings, verifier):
    backend = LiveBackend()

    def hook(record):
        if record["event"] == "APPROVAL_DECISION":
            KillSwitch(settings.kill_switch_file).engage_sentinel()

    outcome = run(settings, incident(*RESTART), approval_callback=approve, backend=backend, on_event=hook)
    assert outcome.status == pipeline.BLOCKED_BY_KILL_SWITCH and backend.done == []


@pytest.mark.parametrize("status, expected", [
    ("NOT_RECOVERED", pipeline.NOT_RECOVERED_IRREVERSIBLE_ESCALATED),
    ("NO_DATA", pipeline.NOT_VERIFIED_NO_DATA_ESCALATED),
])
def test_irreversible_restart_never_rolls_back(settings, verifier, status, expected):
    verifier["status"] = status
    backend = LiveBackend()
    outcome = run(settings, incident(*RESTART), approval_callback=approve, backend=backend)
    assert outcome.status == expected
    assert backend.done == [("action", "ACT-INC-PIPE")]
    assert "ROLLBACK" not in names(outcome) and names(outcome)[-1] == "ESCALATION"
    report = json.loads((Path(settings.report_output_dir) / "INC-PIPE" / "report.json").read_text())
    assert report["remediation"]["pipeline_status"] == expected


def test_irreversible_cli_prompt_warns_first():
    import io
    from tests.test_action_boundary import FakeTTY
    from src.models.action import ActionType, RemediationAction
    from src.approval.gate import cli_approval_callback
    action = RemediationAction(action_id="ACT-R", action_type=ActionType.RESTART_SERVICE, target_service="cart",
                               description="restart", irreversible=True)
    out = io.StringIO()
    decision = cli_approval_callback(stdin=FakeTTY("y\n"), stdout=out, approver="bob")(action)
    text = out.getvalue()
    assert text.index("NO ROLLBACK") < text.index("HUMAN APPROVAL REQUIRED") < text.index("[y/N]")
    assert decision.approved and decision.irreversible_acknowledged


def test_kill_switch_blocks_at_plan(settings, verifier):
    KillSwitch(settings.kill_switch_file).engage_sentinel()
    asked = []
    outcome = run(settings, approval_callback=lambda a: asked.append(a) or True)
    assert outcome.status == pipeline.BLOCKED_BY_KILL_SWITCH
    assert asked == [] and verifier["baseline"] == []
    ks = [r for r in outcome.timeline if r["event"] == "KILL_SWITCH"][0]["data"]
    assert ks["checkpoint"] == "plan" and ks["engaged"] is True
    assert "KILL_SWITCH_ENABLED" not in ks["reason"]


def test_kill_switch_engaged_during_approval_blocks_post_approval(settings, verifier):
    backend = LiveBackend()

    def approve_then_kill(action):
        KillSwitch(settings.kill_switch_file).engage_sentinel()
        return approve(action)

    outcome = run(settings, approval_callback=approve_then_kill, backend=backend)
    assert outcome.status == pipeline.BLOCKED_BY_KILL_SWITCH and backend.done == []
    assert [r["data"]["checkpoint"] for r in outcome.timeline if r["event"] == "KILL_SWITCH"][-1] == "post_approval"


def test_kill_switch_engaged_between_approval_and_execute_blocks_pre_execute(settings, verifier):
    backend = LiveBackend()

    def hook(record):
        if record["event"] == "KILL_SWITCH" and record["data"]["checkpoint"] == "post_approval":
            KillSwitch(settings.kill_switch_file).engage_sentinel()

    outcome = run(settings, approval_callback=approve, backend=backend, on_event=hook)
    assert outcome.status == pipeline.BLOCKED_BY_KILL_SWITCH and backend.done == []
    assert [r["data"]["checkpoint"] for r in outcome.timeline if r["event"] == "KILL_SWITCH"][-1] == "pre_execute"


def test_not_recovered_runs_approved_rollback(settings, verifier):
    verifier["status"] = "NOT_RECOVERED"
    backend = LiveBackend()
    outcome = run(settings, approval_callback=approve, backend=backend)
    assert outcome.status == pipeline.NOT_RECOVERED_ROLLED_BACK
    assert backend.done == [("action", "ACT-INC-PIPE"), ("rollback", "ACT-INC-PIPE-RB")]
    assert "ROLLBACK" in names(outcome) and "ESCALATION" in names(outcome)


def test_no_data_escalates_without_rollback(settings, verifier):
    verifier["status"] = "NO_DATA"
    backend = LiveBackend()
    outcome = run(settings, approval_callback=approve, backend=backend)
    assert outcome.status == pipeline.NOT_VERIFIED_NO_DATA_ESCALATED
    assert backend.done == [("action", "ACT-INC-PIPE")]


def test_recovered(settings, verifier):
    verifier["status"] = "RECOVERED"
    outcome = run(settings, approval_callback=approve, backend=LiveBackend())
    assert outcome.status == pipeline.RECOVERED and outcome.action.recovery_verified


def test_live_without_action_api_is_blocked_before_asking(settings, verifier):
    settings.dry_run_mode = False
    asked = []
    outcome = run(settings, approval_callback=lambda a: asked.append(a) or True, dry_run=False)
    assert outcome.status == pipeline.BLOCKED_ACTION_API_UNAVAILABLE
    assert "BLOCKED: Action API contract not received" in outcome.reason and asked == []


def test_chat_channel_uses_ui_callback(settings, verifier, monkeypatch):
    fake = types.ModuleType("src.approval.chat_ui")
    seen = {}

    def ui_approval_callback(t, s, timeout_seconds=120, **kw):
        seen.update(kw)
        return lambda a: HumanDecision(True, "carol", "chat_ui", "t")

    fake.ui_approval_callback = ui_approval_callback
    monkeypatch.setitem(sys.modules, "src.approval.chat_ui", fake)
    outcome = run(settings, approval_channel="chat_ui")
    assert outcome.status == pipeline.EXECUTED_DRY_RUN and outcome.approval.channel == "chat_ui"
    assert seen["port"] == settings.chat_ui_port and seen["events"] is not None


def test_unknown_channel_rejects(settings, verifier):
    assert run(settings, approval_channel="email").status == pipeline.REJECTED


def test_no_token_or_key_in_any_record(settings, verifier, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-secretsecretsecretsecret")
    outcome = run(settings, approval_callback=approve)
    text = Path(settings.audit_log_path).read_text() + json.dumps(outcome.timeline, default=str)
    assert "sk-secret" not in text and "_nonce" not in text and "ApprovedAction" not in text


def test_quiet_suppresses_echo_but_still_writes_logs(settings, verifier, capsys):
    run(settings, approval_callback=approve, events=EventLog.from_settings(settings, echo=False))
    assert "KILL_SWITCH" not in capsys.readouterr().out
    assert Path(settings.audit_log_path).read_text()
    assert (Path(settings.report_output_dir) / "INC-PIPE" / "run.log").read_text()
    run(settings, approval_callback=approve, events=EventLog.from_settings(settings, echo=True))
    assert "KILL_SWITCH" in capsys.readouterr().out


def test_reviewer_verdict_shown_before_prompt_and_logged(settings, verifier, monkeypatch, capsys):
    import src.agent.reviewer as reviewer
    monkeypatch.setattr(reviewer, "format_review", lambda r: f"Reviewer verdict: {r['verdict'].upper()}")
    t = incident()
    t.gate["review"] = {"verdict": "weakened", "reasons": ["only one signal"]}
    outcome = run(settings, t, approval_callback=approve)
    assert "Reviewer verdict: WEAKENED" in capsys.readouterr().out
    requested = [r for r in outcome.timeline if r["event"] == "APPROVAL_REQUESTED"][0]
    assert requested["data"]["review_verdict"] == "weakened"
    assert [r for r in run(settings, approval_callback=approve).timeline
            if r["event"] == "APPROVAL_REQUESTED"][0]["data"]["review_verdict"] is None
