from pathlib import Path
import pytest
from src.remediation.kill_switch import KillSwitch, KillSwitchEngagedException
from src.approval.gate import ApprovalGate, ApprovalDecision
from src.models.action import RemediationAction, ActionType, ApprovalStatus


def test_kill_switch_disengaged_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    sentinel = tmp_path / ".kill_switch"
    ks = KillSwitch(sentinel_path=sentinel)

    assert ks.is_engaged() is False
    # Guard should not raise
    ks.guard()


def test_kill_switch_engaged_via_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "true")
    sentinel = tmp_path / ".kill_switch"
    ks = KillSwitch(sentinel_path=sentinel)

    assert ks.is_engaged() is True
    with pytest.raises(KillSwitchEngagedException, match="Emergency Kill-Switch is ENGAGED"):
        ks.guard()


def test_kill_switch_engaged_via_sentinel_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    sentinel = tmp_path / ".kill_switch"
    ks = KillSwitch(sentinel_path=sentinel)

    ks.engage_sentinel()
    assert sentinel.exists()
    assert ks.is_engaged() is True

    with pytest.raises(KillSwitchEngagedException):
        ks.guard()

    ks.disengage_sentinel()
    assert ks.is_engaged() is False
    ks.guard()


def test_approval_cannot_be_bypassed() -> None:
    gate = ApprovalGate()
    action = RemediationAction(
        action_id="ACT-001",
        action_type=ActionType.RESTART_SERVICE,
        target_service="cart",
        description="Restart cart",
        requires_approval=False,
    )
    assert gate.request_approval(action) == ApprovalDecision.REJECTED
    assert action.approval_status != ApprovalStatus.APPROVED


def test_kill_switch_reason_names_only_the_active_trigger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    ks = KillSwitch(sentinel_path=tmp_path / ".kill_switch")
    ks.engage_sentinel()
    assert ks.reasons() == [f"sentinel file '{tmp_path / '.kill_switch'}' exists"]
    with pytest.raises(KillSwitchEngagedException) as exc:
        ks.guard()
    assert "KILL_SWITCH_ENABLED" not in str(exc.value)


def test_approval_gate_callback_approval() -> None:
    gate = ApprovalGate(approval_callback=lambda act: True)
    action = RemediationAction(
        action_id="ACT-002",
        action_type=ActionType.RESTART_SERVICE,
        target_service="payment",
        description="Restart payment container",
        requires_approval=True,
    )
    decision = gate.request_approval(action)
    assert decision == ApprovalDecision.APPROVED
    assert action.approval_status == ApprovalStatus.APPROVED


def test_approval_gate_callback_rejection() -> None:
    gate = ApprovalGate(approval_callback=lambda act: False)
    action = RemediationAction(
        action_id="ACT-003",
        action_type=ActionType.RESTART_SERVICE,
        target_service="payment",
        description="Restart payment container",
        requires_approval=True,
    )
    decision = gate.request_approval(action)
    assert decision == ApprovalDecision.REJECTED
    assert action.approval_status == ApprovalStatus.REJECTED
