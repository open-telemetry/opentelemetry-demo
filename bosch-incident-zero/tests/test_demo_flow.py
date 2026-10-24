"""End-to-end demonstration flow: scripted investigation, diagnosis, approval and the CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.agent.__main__ as cli
import src.approval.pipeline as pipeline
from src.agent.agent import IncidentAgent
from src.agent.llm import LLMConfigError, LLMResponse
from src.agent.presenter import format_incident_brief
from src.agent.transcript import Transcript
from src.approval.gate import HumanDecision
from src.approval.pipeline import execute_safety_pipeline
from src.config import Settings
from src.models.action import ActionType, ApprovalStatus, RemediationAction
from src.remediation.verifier import VerificationResult
from tests.test_agent_loop import factory_for, good_diag, investigation_script, toolbox

SPIKE = good_diag(root_cause={"service": "payment", "category": "traffic_spike", "summary": "payment flooded"})


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("KILL_SWITCH_FILE", str(tmp_path / ".kill_switch"))
    monkeypatch.setenv("DRY_RUN_MODE", "true")
    monkeypatch.setattr(pipeline, "capture_baseline", lambda ctx, s, window_minutes=5: {"service": s})
    monkeypatch.setattr(pipeline, "verify_recovery", lambda ctx, a, b, settle_seconds, dry_run, sleep=None, events=None:
                        VerificationResult(status="NOT_VERIFIED_DRY_RUN", recovered=False, before=b))
    return tmp_path


def approve(action):
    return HumanDecision(True, "alice", "test", "2026-10-24T00:00:00Z")


def test_scripted_investigation_to_dry_run_action(env):
    factory = factory_for(investigation_script(), [LLMResponse(text=json.dumps(SPIKE))])
    t = IncidentAgent(toolbox(), factory, output_dir=env / "out").run("payment flood", incident_id="INC-DEMO")
    assert t.gate["final_confidence"] == "high" and not t.gate["escalate"]

    outcome = execute_safety_pipeline(t, settings=Settings(), approval_callback=approve, ctx=object())
    assert outcome.status == "EXECUTED_DRY_RUN"
    assert outcome.action.action_type == ActionType.THROTTLE_LOAD_GENERATOR
    assert outcome.action.rollback.action_type == ActionType.RESTORE_LOAD_GENERATOR
    report = json.loads((env / "out" / "INC-DEMO" / "report.json").read_text())
    assert report["status"] == "MITIGATION_UNVERIFIED"
    assert report["action_taken"]["approver"] == "alice"


def _patch_cli(monkeypatch, diag):
    monkeypatch.setattr(cli, "ToolBox", lambda ctx: toolbox())
    monkeypatch.setattr(cli, "session_factory",
                        lambda: factory_for(investigation_script(), [LLMResponse(text=json.dumps(diag))]))


def test_cli_quiet_runs_end_to_end_and_still_writes_logs(env, monkeypatch, capsys):
    _patch_cli(monkeypatch, SPIKE)
    assert cli.main(["--alert", "payment flood", "--incident-id", "INC-CLI", "--quiet"],
                    approval_callback=approve) == 0
    out = capsys.readouterr().out
    assert "Pipeline outcome: EXECUTED_DRY_RUN" in out
    live = out.split("AUTONOMOUS INCIDENT DIAGNOSIS BRIEF")[0]
    assert "KILL_SWITCH " not in live and "TOOL_CALL" not in live
    assert "Audit log" in out and "Run log" in out
    assert (env / "out" / "INC-CLI" / "run.log").read_text()
    assert "APPROVAL_DECISION" in (env / "audit.jsonl").read_text()


def test_cli_rejects_without_a_terminal(env, monkeypatch, capsys):
    _patch_cli(monkeypatch, SPIKE)
    monkeypatch.setattr("sys.stdin", open("/dev/null"))
    assert cli.main(["--alert", "payment flood", "--incident-id", "INC-REJ"]) == 0
    assert "Pipeline outcome: REJECTED" in capsys.readouterr().out


def test_cli_escalates_when_llm_not_configured(env, monkeypatch, capsys):
    def unconfigured():
        raise LLMConfigError("LLM_API_KEY is not set")

    monkeypatch.setattr(cli, "session_factory", unconfigured)
    assert cli.main(["--alert", "x"]) == 2
    assert "ESCALATED TO HUMAN" in capsys.readouterr().err


def _load_run_demo():
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_demo", Path(__file__).resolve().parents[1] / "scripts" / "run_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_replay_makes_no_llm_call_and_uses_a_fresh_incident_id(env, monkeypatch, capsys):
    factory = factory_for(investigation_script(), [LLMResponse(text=json.dumps(SPIKE))])
    recorded = IncidentAgent(toolbox(), factory, output_dir=env / "out").run("payment flood", incident_id="INC-REC")
    original = (env / "out" / "INC-REC" / "report.json").read_text()
    demo = _load_run_demo()

    def no_llm():
        raise AssertionError("replay must not call the LLM")

    monkeypatch.setattr(demo, "session_factory", no_llm)
    monkeypatch.setattr(demo, "ToolContext", lambda settings: object())
    assert demo.run_demo(replay=str(env / "out" / "INC-REC" / "transcript.json"), quiet=True,
                         approval_callback=approve) == 0
    out = capsys.readouterr().out
    assert "REPLAY" in out and "Pipeline outcome: EXECUTED_DRY_RUN" in out
    replays = [d.name for d in (env / "out").iterdir() if d.name.startswith("REPLAY-INC-REC-")]
    assert len(replays) == 1
    assert (env / "out" / "INC-REC" / "report.json").read_text() == original
    audit = (env / "audit.jsonl").read_text()
    assert "REPLAY of recorded run INC-REC" in audit and "no LLM call in this run" in audit


def test_cli_has_no_auto_approve_flag():
    with pytest.raises(SystemExit):
        cli.main(["--alert", "x", "--auto-approve"])


def test_presenter_formats_clean_brief():
    t = Transcript(incident_id="INC-TEST-003", alert="High error rate on frontend")
    t.finished_at = "2026-10-24T00:00:00Z"
    t.report = {
        "incident_id": "INC-TEST-003",
        "target_service": "frontend",
        "severity": "HIGH",
        "status": "DIAGNOSED",
        "root_cause_summary": "Upstream error cascade",
        "confidence_score": 0.85,
        "evidence": {
            "trace_ids": ["abcdef0123456789abcdef0123456789"],
            "metrics_summary": {"metric:frontend:error_rate": 0.08},
        },
        "remediation": {
            "recommended_action": "Restart frontend",
            "approval_status": "APPROVED",
            "dry_run": True,
            "recovery_verified": True,
        },
    }
    t.diagnosis = {
        "root_cause": {"service": "frontend", "category": "errors_on_operation", "summary": "Upstream error cascade"},
    }
    t.gate = {"final_confidence": "high"}

    action = RemediationAction(
        action_id="ACT-003",
        action_type=ActionType.RESTART_SERVICE,
        target_service="frontend",
        description="Restart frontend",
        approval_status=ApprovalStatus.APPROVED,
        recovery_verified=True,
        execution_result="Restart simulated",
    )

    brief = format_incident_brief(t, action=action)
    assert "INC-TEST-003" in brief
    assert "frontend" in brief
    assert "DIAGNOSED" in brief
    assert "HIGH" in brief
    assert "abcdef0123456789abcdef0123456789" in brief
    assert "RESTART_SERVICE" in brief
    assert "APPROVED" in brief
    assert "VERIFIED" in brief

