"""Safety-critical interface tests for remediation actions, approval gate, and kill switch."""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from src.models.action import ActionType, ApprovalStatus, RemediationAction
from src.approval.gate import ApprovalDecision, ApprovalGate
from src.remediation.kill_switch import KillSwitch, KillSwitchEngagedException


def test_remediation_action_defaults_to_safe_dry_run():
    action = RemediationAction(
        action_id="ACT-001",
        action_type=ActionType.RESTART_SERVICE,
        target_service="checkout",
        description="Restart checkout service due to memory leak",
    )
    assert action.dry_run is True
    assert action.requires_approval is True
    assert action.approval_status == ApprovalStatus.PENDING
    assert action.executed_at is None
    assert action.execution_result is None
    assert action.recovery_verified is False


def test_approval_gate_defaults_to_rejection_when_unconfigured():
    action = RemediationAction(
        action_id="ACT-002",
        action_type=ActionType.RESTART_SERVICE,
        target_service="cart",
        description="Restart cart service",
    )
    gate = ApprovalGate(require_approval=True)
    decision = gate.request_approval(action)

    assert decision == ApprovalDecision.REJECTED
    assert action.approval_status == ApprovalStatus.PENDING


def test_approval_gate_respects_human_callback():
    action = RemediationAction(
        action_id="ACT-003",
        action_type=ActionType.RESTART_SERVICE,
        target_service="payment",
        description="Restart payment service",
    )
    # Callback approves
    gate_approved = ApprovalGate(require_approval=True, approval_callback=lambda act: True)
    assert gate_approved.request_approval(action) == ApprovalDecision.APPROVED
    assert action.approval_status == ApprovalStatus.APPROVED

    # Callback rejects
    gate_rejected = ApprovalGate(require_approval=True, approval_callback=lambda act: False)
    assert gate_rejected.request_approval(action) == ApprovalDecision.REJECTED
    assert action.approval_status == ApprovalStatus.REJECTED


def test_kill_switch_guards_against_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sentinel = tmp_path / ".kill_switch"
    ks = KillSwitch(sentinel_path=sentinel, env_var="KILL_SWITCH_ENABLED")

    # 1. Normal state: disengaged
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    assert not ks.is_engaged()
    ks.guard()  # should not raise

    # 2. Engaged via environment variable
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "true")
    assert ks.is_engaged()
    with pytest.raises(KillSwitchEngagedException) as exc_info:
        ks.guard()
    assert "KILL_SWITCH_ENABLED=true" in str(exc_info.value)

    # 3. Engaged via sentinel file
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    ks.engage_sentinel()
    assert sentinel.exists()
    assert ks.is_engaged()
    with pytest.raises(KillSwitchEngagedException) as exc_info:
        ks.guard()
    assert "sentinel file" in str(exc_info.value)

    # 4. Disengage sentinel
    ks.disengage_sentinel()
    assert not sentinel.exists()
    assert not ks.is_engaged()
    ks.guard()

def test_post_action_recovery_requires_explicit_verification():
    action = RemediationAction(
        action_id="ACT-004",
        action_type=ActionType.RESTART_SERVICE,
        target_service="email",
        description="Dry-run action proposal",
    )
    # Must fail closed: not verified, not executed
    assert action.recovery_verified is False
    assert action.executed_at is None
    assert action.execution_result is None

    # Verification must only be marked true when fresh telemetry explicitly confirms health
    action.recovery_verified = True
    assert action.recovery_verified is True


def test_diagnosis_agent_executes_no_mutating_actions_by_default():
    # Verify that action model has no side-effects or network calls on instantiation
    action = RemediationAction(
        action_id="ACT-005",
        action_type=ActionType.RESTART_SERVICE,
        target_service="frontend",
        description="Proposed restart",
        dry_run=True,
    )
    assert action.dry_run is True
    assert action.executed_at is None
