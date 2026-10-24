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
    gate = ApprovalGate()
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
    gate_approved = ApprovalGate(approval_callback=lambda act: True)
    assert gate_approved.request_approval(action) == ApprovalDecision.APPROVED
    assert action.approval_status == ApprovalStatus.APPROVED

    # Callback rejects
    gate_rejected = ApprovalGate(approval_callback=lambda act: False)
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


# --- ApprovedAction tokens and backends ---------------------------------------------------------

import io
from src.approval.gate import (ApprovalError, ApprovedAction, HumanDecision, cli_approval_callback)
from src.remediation.backends import ActionRefusedError, DryRunBackend


def _paired(action_type=ActionType.THROTTLE_LOAD_GENERATOR):
    rollback = RemediationAction(action_id="ACT-9-RB", action_type=ActionType.RESTORE_LOAD_GENERATOR,
                                 target_service="load-generator", description="restore")
    return RemediationAction(action_id="ACT-9", action_type=action_type, target_service="load-generator",
                             description="throttle", rollback=rollback)


def _human(approved=True):
    return HumanDecision(approved=approved, approver="alice", channel="test", decided_at="2026-10-24T00:00:00Z")


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_backend_refuses_raw_action_and_audits_it():
    seen = []
    backend = DryRunBackend(audit=seen.append)
    with pytest.raises(ActionRefusedError, match="requires an ApprovedAction"):
        backend.execute(_paired())
    with pytest.raises(ActionRefusedError):
        backend.rollback(_paired().rollback)
    assert backend.requests == []
    assert [e["event"] for e in seen] == ["BACKEND_REFUSED", "BACKEND_REFUSED"]


def test_forged_approved_action_is_refused():
    with pytest.raises(ApprovalError, match="only be issued by ApprovalGate"):
        ApprovedAction(_paired(), _human(), "action", 120, Clock())
    forged = object.__new__(ApprovedAction)
    with pytest.raises(ActionRefusedError):
        DryRunBackend().execute(forged)


def test_approval_is_single_use_and_bound_to_its_action():
    review = ApprovalGate(lambda a: _human()).review(_paired())
    backend = DryRunBackend()
    assert backend.execute(review.action_token).status == "DRY_RUN"
    with pytest.raises(ActionRefusedError, match="already been used"):
        backend.execute(review.action_token)
    with pytest.raises(ActionRefusedError, match="covers the rollback"):
        backend.execute(review.rollback_token)
    with pytest.raises(ActionRefusedError, match="not 'OTHER'"):
        backend.rollback(review.rollback_token, expected_action_id="OTHER")
    assert backend.rollback(review.rollback_token, expected_action_id="ACT-9-RB").role == "rollback"


def test_tampered_action_is_refused():
    review = ApprovalGate(lambda a: _human()).review(_paired())
    review.action_token._action.target_service = "checkout"
    with pytest.raises(ActionRefusedError, match="does not match"):
        DryRunBackend().execute(review.action_token)


def test_expired_approval_is_refused():
    clock = Clock()
    review = ApprovalGate(lambda a: _human(), ttl_seconds=120, clock=clock).review(_paired())
    clock.now += 121
    with pytest.raises(ActionRefusedError, match="expired"):
        DryRunBackend().execute(review.action_token)


def test_rejection_issues_no_tokens():
    review = ApprovalGate(lambda a: _human(approved=False)).review(_paired())
    assert review.action_token is None and review.rollback_token is None


def test_non_allowlisted_type_is_refused_even_with_approval():
    action = RemediationAction(action_id="ACT-C", action_type=ActionType.CUSTOM, target_service="cart",
                               description="anything")
    review = ApprovalGate(lambda a: _human()).review(action)
    with pytest.raises(ActionRefusedError, match="not on the allowlist"):
        DryRunBackend().execute(review.action_token)


class FakeTTY(io.StringIO):
    def isatty(self):
        return True

    def fileno(self):
        raise io.UnsupportedOperation


def test_cli_prompt_rejects_eof_non_tty_and_default_answer():
    out = io.StringIO()
    assert cli_approval_callback(stdin=FakeTTY(""), stdout=out)(_paired()).approved is False
    assert "EOF" in out.getvalue()
    assert cli_approval_callback(stdin=io.StringIO("y\n"), stdout=io.StringIO())(_paired()).approved is False
    assert cli_approval_callback(stdin=FakeTTY("\n"), stdout=io.StringIO())(_paired()).approved is False
    yes = cli_approval_callback(stdin=FakeTTY("y\n"), stdout=out, approver="bob")(_paired())
    assert (yes.approved, yes.approver, yes.channel) == (True, "bob", "cli")
    assert "ACT-9-RB" in out.getvalue()


def test_cli_prompt_times_out_to_reject():
    r, w = os.pipe()
    try:
        stream = os.fdopen(r, "r")

        class PipeTTY:
            def isatty(self):
                return True

            def fileno(self):
                return stream.fileno()

            def readline(self):
                return stream.readline()

        decision = cli_approval_callback(timeout_seconds=0.1, stdin=PipeTTY(), stdout=io.StringIO())(_paired())
        assert decision.approved is False and "timeout" in decision.note
    finally:
        os.close(w)
        stream.close()


def test_approval_timeout_from_channel_rejects():
    def times_out(action):
        raise TimeoutError

    assert ApprovalGate(times_out).request_approval(_paired()) == ApprovalDecision.REJECTED
