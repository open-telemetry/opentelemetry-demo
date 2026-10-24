"""Safety pipeline orchestrating human approval, kill-switch verification, and dry-run remediation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..config import Settings
from ..models.action import ActionType, ApprovalStatus, RemediationAction
from .gate import ApprovalDecision, ApprovalGate
from ..remediation.kill_switch import KillSwitch, KillSwitchEngagedException
from ..agent.transcript import Transcript, utc_now
from ..agent.tools import ToolContext, container_health


def log_audit_event(audit_log_path: Path | str, event: Dict[str, Any]) -> None:
    """Append a structured audit event to the audit log."""
    path = Path(audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def execute_safety_pipeline(
    transcript: Transcript,
    settings: Optional[Settings] = None,
    approval_callback: Optional[Callable[[RemediationAction], bool]] = None,
    interactive: bool = False,
    auto_approve: bool = False,
    ctx: Optional[ToolContext] = None,
) -> RemediationAction:
    """Evaluate kill-switch, request approval, and perform safe dry-run remediation with verification."""
    cfg = settings or Settings()
    audit_path = Path(cfg.audit_log_path)
    if not audit_path.is_absolute():
        audit_path = cfg.root_dir / audit_path

    target_service = transcript.report.get("target_service") or "unknown"
    remediation_info = transcript.report.get("remediation", {}) or {}
    action_desc = remediation_info.get("recommended_action") or f"Restart service {target_service}"

    action = RemediationAction(
        action_id=remediation_info.get("action_id") or f"ACT-{transcript.incident_id}",
        action_type=ActionType.RESTART_SERVICE,
        target_service=target_service,
        description=action_desc,
        dry_run=True,
        requires_approval=True,
    )

    # 1. Kill-Switch Guard
    ks = KillSwitch(sentinel_path=cfg.kill_switch_file, env_var="KILL_SWITCH_ENABLED")
    if ks.is_engaged():
        reasons = []
        if ks.sentinel_path.exists():
            reasons.append(f"sentinel file '{ks.sentinel_path}'")
        if ks.is_engaged():
            reasons.append(f"{ks.env_var}=true")
        reason_str = " and ".join(reasons) if reasons else "emergency stop active"

        event = {
            "timestamp": utc_now(),
            "event": "ACTION_HALTED_BY_KILL_SWITCH",
            "incident_id": transcript.incident_id,
            "action_id": action.action_id,
            "target_service": action.target_service,
            "reason": reason_str,
        }
        log_audit_event(audit_path, event)
        transcript.report["remediation"]["approval_status"] = "BLOCKED_BY_KILL_SWITCH"
        transcript.report["remediation"]["executed_at"] = None
        action.approval_status = ApprovalStatus.REJECTED
        return action

    # 2. Human Approval Gate
    def _interactive_prompt(act: RemediationAction) -> bool:
        try:
            resp = input(
                f"\n[APPROVAL GATE] Proposed Remediation: {act.action_type.value} on target '{act.target_service}' "
                f"(Mode: DRY_RUN). Approve action? [y/N]: "
            )
            return resp.strip().lower() in ("y", "yes")
        except EOFError:
            return False

    callback = approval_callback
    if callback is None:
        if auto_approve:
            callback = lambda act: True
        elif interactive:
            callback = _interactive_prompt
        else:
            callback = lambda act: False

    gate = ApprovalGate(require_approval=cfg.require_human_approval, approval_callback=callback)
    decision = gate.request_approval(action)

    if decision != ApprovalDecision.APPROVED:
        event = {
            "timestamp": utc_now(),
            "event": "ACTION_REJECTED",
            "incident_id": transcript.incident_id,
            "action_id": action.action_id,
            "target_service": action.target_service,
            "decision": "REJECTED",
        }
        log_audit_event(audit_path, event)
        transcript.report["remediation"]["approval_status"] = ApprovalStatus.REJECTED.value
        transcript.report["remediation"]["executed_at"] = None
        return action

    # 3. Safe Dry-Run Action Execution
    action.executed_at = utc_now()
    action.execution_result = (
        f"Simulated Action API dry-run execution: {action.action_type.value} target '{action.target_service}' "
        "completed without error (dry_run: true)."
    )

    # 4. Post-Action Recovery Verification
    context = ctx or ToolContext(cfg)
    try:
        health = container_health(context, service=action.target_service)
        if health.get("status") == "ok":
            action.recovery_verified = True
        else:
            action.recovery_verified = False
    except Exception:
        action.recovery_verified = False

    # 5. Audit Logging & Report Update
    event = {
        "timestamp": action.executed_at,
        "event": "ACTION_EXECUTED_DRY_RUN",
        "incident_id": transcript.incident_id,
        "action_id": action.action_id,
        "action_type": action.action_type.value,
        "target_service": action.target_service,
        "dry_run": action.dry_run,
        "approval_status": action.approval_status.value,
        "recovery_verified": action.recovery_verified,
        "execution_result": action.execution_result,
    }
    log_audit_event(audit_path, event)

    transcript.report["remediation"].update({
        "action_id": action.action_id,
        "approval_status": action.approval_status.value,
        "dry_run": action.dry_run,
        "executed_at": action.executed_at,
        "recovery_verified": action.recovery_verified,
    })

    # Resave updated report to transcript output dir
    if transcript.incident_id:
        out_dir = Path(cfg.report_output_dir)
        if not out_dir.is_absolute():
            out_dir = cfg.root_dir / out_dir
        target_file = out_dir / transcript.incident_id / "report.json"
        if target_file.parent.exists():
            target_file.write_text(json.dumps(transcript.report, indent=2, default=str), encoding="utf-8")

    return action

