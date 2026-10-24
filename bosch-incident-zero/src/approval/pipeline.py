"""Safety pipeline: plan, kill switch, baseline, human approval, kill switch twice, execute,
verify, and an approved rollback on measured non-recovery. Every step is a run event."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..agent.report import attach_action_outcome, write_report_files
from ..agent.tools import ToolContext
from ..agent.transcript import Transcript
from ..config import Settings
from ..events import EventLog
from ..models.action import RemediationAction, is_allowlisted
from ..remediation.backends import (ActionAPINotConfiguredError, ActionBackend, ActionRefusedError,
                                    ActionResult, get_backend)
from ..remediation.kill_switch import KillSwitch
from ..remediation.planner import plan_with_reason
from ..remediation.verifier import NOT_RECOVERED, VerificationResult, capture_baseline, verify_recovery
from .gate import ApprovalDecision, ApprovalGate, HumanDecision, cli_approval_callback

NO_ACTION_ESCALATED = "NO_ACTION_ESCALATED"
BLOCKED_BY_KILL_SWITCH = "BLOCKED_BY_KILL_SWITCH"
REJECTED = "REJECTED"
BLOCKED_ACTION_API_UNAVAILABLE = "BLOCKED_ACTION_API_UNAVAILABLE"
ACTION_REFUSED = "ACTION_REFUSED"
EXECUTION_FAILED = "EXECUTION_FAILED"
EXECUTED_DRY_RUN = "EXECUTED_DRY_RUN"
RECOVERED = "RECOVERED"
NOT_RECOVERED_ROLLED_BACK = "NOT_RECOVERED_ROLLED_BACK"
NOT_RECOVERED_ROLLBACK_FAILED = "NOT_RECOVERED_ROLLBACK_FAILED"
NOT_VERIFIED_NO_DATA_ESCALATED = "NOT_VERIFIED_NO_DATA_ESCALATED"
NOT_RECOVERED_IRREVERSIBLE_ESCALATED = "NOT_RECOVERED_IRREVERSIBLE_ESCALATED"
APPROVAL_CHANNELS = ("cli", "chat_ui")
CHECKPOINTS = {1: "plan", 2: "post_approval", 3: "pre_execute", 4: "pre_rollback"}
BASELINE_WINDOW_MINUTES = 5
# Extra validity for the rollback approval so it survives the settle wait and the after-snapshot.
ROLLBACK_TTL_MARGIN_SECONDS = 300


@dataclass
class PipelineOutcome:
    status: str
    action: Optional[RemediationAction] = None
    verification: Optional[VerificationResult] = None
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    approval: Optional[HumanDecision] = None
    result: Optional[ActionResult] = None
    rollback_result: Optional[ActionResult] = None
    report_paths: Dict[str, Any] = field(default_factory=dict)

    @property
    def escalated(self) -> bool:
        return self.status not in (RECOVERED, EXECUTED_DRY_RUN)


class _Trail:
    def __init__(self, events: EventLog, on_event: Optional[Callable[[Dict[str, Any]], None]]):
        self.events = events
        self.on_event = on_event
        self.start = len(events.records)

    def __call__(self, event: str, summary: str, **data: Any) -> Dict[str, Any]:
        record = self.events.emit(event, summary, data)
        if self.on_event:
            self.on_event(record)
        return record

    def refusal(self, entry: Dict[str, Any]) -> None:
        self("ACTION_REFUSED", f"{entry.get('backend')} refused {entry.get('operation')} of "
                               f"{entry.get('action_id')}: {entry.get('reason')}",
             **{k: entry.get(k) for k in ("backend", "operation", "action_id", "reason")})

    @property
    def timeline(self) -> List[Dict[str, Any]]:
        return list(self.events.records[self.start:])


def _summary(action: Optional[RemediationAction]) -> Optional[Dict[str, Any]]:
    if action is None:
        return None
    return {"action_id": action.action_id, "action_type": action.action_type.value,
            "target_service": action.target_service, "reason": action.parameters.get("reason")}


def _describe(action: RemediationAction) -> str:
    return f"{action.action_type.value} -> {action.target_service}"


def _kill_switch_reasons(ks: KillSwitch, cfg: Settings) -> List[str]:
    reasons = ks.reasons()
    if cfg.kill_switch_enabled and not any(ks.env_var in r for r in reasons):
        reasons.append(f"{ks.env_var}=true in the settings/.env file")
    return reasons


def _resolve_callback(injected: Optional[Callable], channel: str, transcript: Transcript, cfg: Settings,
                      open_browser: bool, events: EventLog) -> Callable:
    if injected is not None:
        return injected
    if channel == "chat_ui":
        from .chat_ui import ui_approval_callback
        return ui_approval_callback(transcript, cfg, timeout_seconds=cfg.approval_timeout_seconds,
                                    port=cfg.chat_ui_port, events=events, open_browser=open_browser,
                                    on_ready=lambda url: print(f"Chat approval UI: {url}", flush=True))
    if channel == "cli":
        return cli_approval_callback(timeout_seconds=cfg.approval_timeout_seconds)
    raise ValueError(f"unknown approval channel '{channel}' (expected one of {APPROVAL_CHANNELS})")


def _run(transcript: Transcript, cfg: Settings, emit: _Trail, approval_callback: Optional[Callable],
         approval_channel: str, dry_run: bool, ctx: Optional[ToolContext], backend: Optional[ActionBackend],
         sleep: Callable[[float], None], clock: Callable[[], float], open_browser: bool) -> PipelineOutcome:
    def outcome(status: str, action: Optional[RemediationAction] = None, reason: str = "", **kw: Any) -> PipelineOutcome:
        return PipelineOutcome(status=status, action=action, reason=reason, **kw)

    plan = plan_with_reason(transcript, cfg.deploy_platform)
    action = plan.action
    if action is None:
        emit("PLAN", f"no action: escalated ({plan.reason})", action=None, rollback=None, reason=plan.reason)
        return outcome(NO_ACTION_ESCALATED, None, plan.reason)
    rb = action.rollback
    emit("PLAN", f"{_describe(action)}; rollback: {_describe(rb) if rb else 'none'}",
         action=_summary(action), rollback=_summary(rb), reason=plan.reason)
    for act in (action, rb):
        if act is not None and not is_allowlisted(act.action_type):
            return outcome(NO_ACTION_ESCALATED, action, f"{act.action_type.value} is not on the action allowlist")
    if rb is None and not action.irreversible:
        return outcome(NO_ACTION_ESCALATED, action, f"no approved rollback: {action.action_type.value} has no "
                                                    f"rollback action in the action catalog")

    try:
        be = backend or get_backend(cfg, dry_run=dry_run, audit=emit.refusal)
    except ActionAPINotConfiguredError as e:
        return outcome(BLOCKED_ACTION_API_UNAVAILABLE, action, str(e))
    if be.audit is None:
        be.audit = emit.refusal
    for act in (action, rb):
        if act is None:
            continue
        act.dry_run = be.dry_run
        act.backend = be.name

    ks = KillSwitch(sentinel_path=cfg.resolve_path(cfg.kill_switch_file), env_var="KILL_SWITCH_ENABLED")

    def kill_switch_clear(check: int, act: RemediationAction) -> bool:
        reason = " and ".join(_kill_switch_reasons(ks, cfg))
        checkpoint = CHECKPOINTS[check]
        emit("KILL_SWITCH", f"{checkpoint}: {'ENGAGED, ' + reason if reason else 'clear'}",
             checkpoint=checkpoint, engaged=bool(reason), reason=reason or None, action_id=act.action_id)
        return not reason

    halted = "emergency kill switch is engaged"
    if not kill_switch_clear(1, action):
        return outcome(BLOCKED_BY_KILL_SWITCH, action, halted)

    context = ctx or ToolContext(cfg)
    verify_service = action.parameters.get("diagnosed_service") or action.target_service
    try:
        baseline = capture_baseline(context, verify_service, window_minutes=BASELINE_WINDOW_MINUTES)
    except Exception as e:
        baseline = {"service": verify_service, "window_minutes": BASELINE_WINDOW_MINUTES,
                    "error": f"baseline capture failed: {e}"}

    timeout = cfg.approval_timeout_seconds
    review_result = (transcript.gate or {}).get("review")
    review_verdict = review_result.get("verdict") if isinstance(review_result, dict) else None
    if review_verdict is not None and approval_channel == "cli":
        from ..agent.reviewer import format_review
        print(format_review(review_result), flush=True)
    rb_text = _describe(rb) if rb else "NONE (irreversible)"
    emit("APPROVAL_REQUESTED", f"{_describe(action)} with rollback {rb_text} via {approval_channel}, "
                               f"timeout {timeout}s",
         action=_summary(action), rollback=_summary(rb), channel=approval_channel, timeout_seconds=timeout,
         dry_run=be.dry_run, baseline_service=verify_service, review_verdict=review_verdict,
         irreversible=action.irreversible)

    def decision_event(approved: bool, approver: Any, channel: Any, note: str, decided_at: Any = None,
                       acknowledged: bool = False) -> None:
        emit("APPROVAL_DECISION", f"{'APPROVED' if approved else 'REJECTED'} by {approver or 'nobody'} "
                                  f"via {channel}{': ' + note if note else ''}",
             approved=approved, approver=approver, channel=channel, note=note, decided_at=decided_at,
             action_id=action.action_id, rollback_action_id=rb.action_id if rb else None,
             irreversible_acknowledged=acknowledged)

    try:
        callback = _resolve_callback(approval_callback, approval_channel, transcript, cfg, open_browser,
                                     emit.events)
    except Exception as e:
        reason = f"approval channel '{approval_channel}' unavailable: {e}"
        decision_event(False, None, approval_channel, reason)
        return outcome(REJECTED, action, reason)
    gate = ApprovalGate(callback, ttl_seconds=cfg.approval_ttl_seconds, clock=clock,
                        rollback_ttl_seconds=(cfg.approval_ttl_seconds + cfg.action_settle_seconds
                                              + ROLLBACK_TTL_MARGIN_SECONDS))
    review = gate.review(action)
    human = review.human
    if human is None:
        decision_event(False, None, approval_channel, review.reason)
    else:
        decision_event(human.approved is True and review.decision == ApprovalDecision.APPROVED,
                       human.approver, human.channel, human.note, human.decided_at,
                       human.irreversible_acknowledged)
    if review.decision != ApprovalDecision.APPROVED:
        return outcome(REJECTED, action, review.reason or "rejected by human", approval=human)
    if review.rollback_token is None and not (action.irreversible and human.irreversible_acknowledged):
        return outcome(NO_ACTION_ESCALATED, action, "no approved rollback", approval=human)

    if not kill_switch_clear(2, action) or not kill_switch_clear(3, action):
        return outcome(BLOCKED_BY_KILL_SWITCH, action, halted, approval=human)

    try:
        result = be.execute(review.action_token, expected_action_id=action.action_id)
    except ActionRefusedError as e:
        return outcome(ACTION_REFUSED, action, str(e), approval=human)
    except ActionAPINotConfiguredError as e:
        return outcome(BLOCKED_ACTION_API_UNAVAILABLE, action, str(e), approval=human)
    except Exception as e:
        emit("ERROR", f"action {action.action_id} failed: {e}", action_id=action.action_id, error=str(e))
        return outcome(EXECUTION_FAILED, action, f"action failed: {e}", approval=human)
    action.executed_at = result.timestamp
    action.execution_result = result.message
    emit("DRY_RUN" if result.dry_run else "ACTION_EXECUTED", result.message, **result.to_dict())

    settle = 0 if be.dry_run else cfg.action_settle_seconds
    try:
        verification = verify_recovery(context, action, baseline, settle_seconds=settle,
                                       dry_run=be.dry_run, sleep=sleep, events=emit.events)
    except Exception as e:
        verification = VerificationResult(status="NO_DATA", recovered=False, before=baseline,
                                          reasons=[f"verification failed: {e}"])
        emit("VERIFICATION", f"NO_DATA: verification failed: {e}", status="NO_DATA", recovered=False,
             reasons=verification.reasons)

    done = {"approval": human, "result": result, "verification": verification}
    if be.dry_run:
        return outcome(EXECUTED_DRY_RUN, action, "dry run recorded; recovery is not claimed", **done)
    if verification.status == RECOVERED:
        action.recovery_verified = True
        return outcome(RECOVERED, action, "fresh telemetry shows recovery", **done)
    if verification.status != NOT_RECOVERED:
        return outcome(NOT_VERIFIED_NO_DATA_ESCALATED, action,
                       f"recovery could not be verified ({verification.status}); no rollback", **done)

    if action.irreversible:
        return outcome(NOT_RECOVERED_IRREVERSIBLE_ESCALATED, action,
                       "no recovery measured after an irreversible action; nothing to roll back, escalating", **done)
    if not kill_switch_clear(4, rb):
        return outcome(BLOCKED_BY_KILL_SWITCH, action, "no recovery measured and the kill switch blocked the "
                                                       "rollback; a human must restore state", **done)
    try:
        rb_result = be.rollback(review.rollback_token, expected_action_id=rb.action_id)
    except Exception as e:
        emit("ROLLBACK", f"rollback {rb.action_id} FAILED: {e}", ok=False, action_id=rb.action_id, error=str(e))
        return outcome(NOT_RECOVERED_ROLLBACK_FAILED, action, f"no recovery measured and the rollback failed: {e}",
                       **done)
    rb.executed_at = rb_result.timestamp
    rb.execution_result = rb_result.message
    emit("ROLLBACK", rb_result.message, ok=True, **rb_result.to_dict())
    return outcome(NOT_RECOVERED_ROLLED_BACK, action, "no recovery measured; the approved rollback was executed",
                   rollback_result=rb_result, **done)


def _finalize(transcript: Transcript, cfg: Settings, outcome: PipelineOutcome, events: EventLog) -> None:
    if transcript.report is None:
        return
    report = dict(transcript.report)
    remediation = dict(report.get("remediation") or {})
    remediation["pipeline_status"] = outcome.status
    remediation["pipeline_reason"] = outcome.reason
    if outcome.status == BLOCKED_BY_KILL_SWITCH:
        remediation["approval_status"] = "BLOCKED_BY_KILL_SWITCH"
    report["remediation"] = remediation
    shown = outcome.action if outcome.approval is not None else None
    audit = events.audit_log_path or cfg.resolve_path(cfg.audit_log_path)
    transcript.report = attach_action_outcome(report, shown, outcome.verification, outcome.timeline, str(audit),
                                                rollback_result=outcome.rollback_result)
    out_dir = cfg.resolve_path(cfg.report_output_dir)
    transcript.save(out_dir)
    outcome.report_paths = write_report_files(transcript.report, out_dir, events=events)


def execute_safety_pipeline(
    transcript: Transcript,
    settings: Optional[Settings] = None,
    approval_callback: Optional[Callable[[RemediationAction], Any]] = None,
    approval_channel: str = "cli",
    dry_run: bool = True,
    ctx: Optional[ToolContext] = None,
    backend: Optional[ActionBackend] = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    events: Optional[EventLog] = None,
    open_browser: bool = False,
) -> PipelineOutcome:
    """Run the remediation safety pipeline for one diagnosed incident.

    approval_callback is for tests only; product code asks a human on approval_channel.
    on_event is called with every record right after it is emitted.
    """
    cfg = settings or Settings()
    events = events or EventLog.from_settings(cfg, echo=False)
    events.bind(transcript.incident_id)
    emit = _Trail(events, on_event)
    outcome = _run(transcript, cfg, emit, approval_callback, approval_channel, dry_run, ctx, backend,
                   sleep, clock, open_browser)
    if outcome.escalated:
        emit("ESCALATION", f"{outcome.status}: {outcome.reason}", status=outcome.status, reason=outcome.reason,
             action_id=outcome.action.action_id if outcome.action else None)
    outcome.timeline = emit.timeline
    _finalize(transcript, cfg, outcome, events)
    return outcome
