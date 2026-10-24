"""Integration and unit tests for the end-to-end demonstration flow."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from src.agent.llm import AutonomousInvestigationSession
from src.agent.presenter import format_incident_brief
from src.agent.transcript import Transcript
from src.approval.pipeline import execute_safety_pipeline, log_audit_event
from src.config import Settings
from src.models.action import ActionType, ApprovalStatus, RemediationAction
from src.remediation.kill_switch import KillSwitch


def test_autonomous_session_investigation_and_diagnosis_flow():
    # 1. Investigation phase
    tools = [{"name": "system_overview", "description": "overview", "parameters": {}}]
    session = AutonomousInvestigationSession(system="investigate", tools=tools)

    resp1 = session.send(user_text="ALERT: High latency on recommendation service")
    assert len(resp1.tool_calls) == 6
    called_names = [tc.name for tc in resp1.tool_calls]
    assert "system_overview" in called_names
    assert "get_service_metrics" in called_names
    assert "search_traces" in called_names

    # 2. Diagnosis phase
    diag_session = AutonomousInvestigationSession(system="diagnose", tools=[])
    diag_prompt = (
        "ALERT: High latency on recommendation\n\n"
        "INVESTIGATOR FINDINGS: p95 high\n\n"
        "TOOL TRANSCRIPT (JSON):\n"
        '[{"n": 1, "tool": "search_traces", "arguments": {}, "result": {"evidence": [{"kind": "trace", "ref": "1234567890abcdef1234567890abcdef"}]}}, '
        '{"n": 2, "tool": "container_health", "arguments": {}, "result": {"evidence": [{"kind": "container", "ref": "container:recommendation:state", "value": "running"}]}}]'
        "\n\nReturn the diagnosis JSON now."
    )
    resp_diag = diag_session.send(user_text=diag_prompt)
    assert resp_diag.text.strip().startswith("{")
    diag_data = json.loads(resp_diag.text)
    assert diag_data["verdict"] == "diagnosed"
    assert diag_data["confidence"] == "high"
    assert len(diag_data["evidence"]) >= 1


def test_safety_pipeline_executes_and_audits(tmp_path: Path):
    audit_file = tmp_path / "test_audit.jsonl"
    report_dir = tmp_path / "incident_output"
    settings = Settings()
    settings.audit_log_path = str(audit_file)
    settings.report_output_dir = str(report_dir)
    settings.require_human_approval = True

    t = Transcript(incident_id="INC-TEST-001", alert="Checkout degradation")
    t.finished_at = "2026-10-24T00:00:00Z"
    t.report = {
        "incident_id": "INC-TEST-001",
        "target_service": "checkout",
        "remediation": {"recommended_action": "Restart checkout"},
    }
    t.save(report_dir)

    # Mock tool context for recovery verification
    mock_ctx = SimpleNamespace()
    action = execute_safety_pipeline(
        t,
        settings=settings,
        auto_approve=True,
        ctx=mock_ctx,
    )

    assert action.approval_status == ApprovalStatus.APPROVED
    assert action.dry_run is True
    assert action.executed_at is not None
    assert audit_file.exists()
    audit_lines = audit_file.read_text().splitlines()
    assert len(audit_lines) == 1
    event = json.loads(audit_lines[0])
    assert event["event"] == "ACTION_EXECUTED_DRY_RUN"
    assert event["incident_id"] == "INC-TEST-001"


def test_safety_pipeline_kill_switch_blocks(tmp_path: Path):
    audit_file = tmp_path / "test_audit.jsonl"
    sentinel = tmp_path / ".kill_switch"
    settings = Settings()
    settings.audit_log_path = str(audit_file)
    settings.kill_switch_file = str(sentinel)
    settings.require_human_approval = True

    ks = KillSwitch(sentinel_path=sentinel)
    ks.engage_sentinel()

    t = Transcript(incident_id="INC-TEST-002", alert="Payment timeout")
    t.report = {
        "incident_id": "INC-TEST-002",
        "target_service": "payment",
        "remediation": {"recommended_action": "Restart payment"},
    }

    action = execute_safety_pipeline(t, settings=settings, auto_approve=True)

    assert action.approval_status == ApprovalStatus.REJECTED
    assert t.report["remediation"]["approval_status"] == "BLOCKED_BY_KILL_SWITCH"
    assert audit_file.exists()
    event = json.loads(audit_file.read_text().splitlines()[0])
    assert event["event"] == "ACTION_HALTED_BY_KILL_SWITCH"

    ks.disengage_sentinel()


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

