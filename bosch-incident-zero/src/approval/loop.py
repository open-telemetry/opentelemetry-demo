"""Closed remediation loop: investigate, plan, a fresh human approval, execute, settle, verify.

Another attempt runs only after a measured non-recovery on a live backend; everything else stops the loop.
report.json and report.md are written once, after the loop has ended.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..agent.tools import ToolContext
from ..agent.transcript import Transcript
from ..config import Settings, load_env_file
from ..events import EventLog
from ..remediation.backends import ActionBackend
from .pipeline import (BLOCKED_BY_KILL_SWITCH, EXECUTED_DRY_RUN, NON_OPERATIVE_PARAMS,
                       NOT_RECOVERED_IRREVERSIBLE_ESCALATED, NOT_RECOVERED_ROLLED_BACK, RECOVERED, REJECTED,
                       PipelineOutcome, _snapshot_view, _Trail, action_signature, finalize_report,
                       kill_switch_reasons, run_attempt)

DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS_CAP = 5
RETRY_STATUSES = frozenset({NOT_RECOVERED_ROLLED_BACK, NOT_RECOVERED_IRREVERSIBLE_ESCALATED})
RESOLVED_VERIFIED = "RESOLVED_VERIFIED"
UNRESOLVED_ESCALATED = "UNRESOLVED_ESCALATED"
NOT_VERIFIED_DRY_RUN = "NOT_VERIFIED_DRY_RUN"

Investigator = Callable[[Optional[str], List[Dict[str, Any]]], Transcript]


def clamp_attempts(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_MAX_ATTEMPTS
    return max(1, min(MAX_ATTEMPTS_CAP, n))


def configured_max_attempts(cfg: Settings) -> int:
    """REMEDIATION_MAX_ATTEMPTS from the environment or .env, clamped to 1..MAX_ATTEMPTS_CAP."""
    raw = os.environ.get("REMEDIATION_MAX_ATTEMPTS",
                         load_env_file(cfg.root_dir / ".env").get("REMEDIATION_MAX_ATTEMPTS", ""))
    return clamp_attempts(raw or DEFAULT_MAX_ATTEMPTS)


def final_status(last: PipelineOutcome, attempts: int, max_attempts: int) -> Tuple[str, str]:
    if last.status == RECOVERED:
        return RESOLVED_VERIFIED, f"fresh telemetry shows the symptom cleared after attempt {attempts}"
    if last.status == EXECUTED_DRY_RUN:
        return NOT_VERIFIED_DRY_RUN, "dry run: nothing changed, so recovery is not claimed and no retry is made"
    if last.status in (REJECTED, BLOCKED_BY_KILL_SWITCH):
        return last.status, last.reason
    if last.status in RETRY_STATUSES:
        return UNRESOLVED_ESCALATED, (f"{attempts} of {max_attempts} attempt(s) did not recover the symptom; "
                                      f"attempts exhausted, escalating to a human ({last.reason})")
    return UNRESOLVED_ESCALATED, f"{last.status}: {last.reason}"


def prior_context(o: PipelineOutcome) -> Dict[str, Any]:
    """What the next investigation is told about a failed attempt (a hint, never evidence)."""
    a, v = o.action, o.verification
    root = ((o.transcript.diagnosis if o.transcript else None) or {}).get("root_cause") or {}
    return {
        "attempt": o.attempt,
        "action_type": a.action_type.value if a else None,
        "target_service": a.target_service if a else None,
        "parameters": {k: val for k, val in (a.parameters if a else {}).items() if k not in NON_OPERATIVE_PARAMS},
        "diagnosed_service": root.get("service"),
        "category": root.get("category"),
        "verification": None if v is None else {
            "status": v.status, "before": _snapshot_view(v.before), "after": _snapshot_view(v.after),
            "reasons": list(v.reasons)[:6]},
        "outcome": o.status,
        "rollback_ran": o.rollback_result is not None,
    }


def _save_attempt(t: Transcript, cfg: Settings, attempt: int, prior: List[Dict[str, Any]]) -> None:
    folder = cfg.resolve_path(cfg.report_output_dir) / t.incident_id / "attempts"
    folder.mkdir(parents=True, exist_ok=True)
    body = {k: v for k, v in t.to_dict().items() if k != "report"}
    body.update(attempt=attempt, prior_attempts=prior)
    (folder / f"attempt-{attempt}.transcript.json").write_text(json.dumps(body, indent=2, default=str))


def run_remediation_loop(
    alert: str,
    settings: Optional[Settings] = None,
    investigate: Optional[Investigator] = None,
    first_transcript: Optional[Transcript] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    approval_callback: Optional[Callable[[Any], Any]] = None,
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
    """Repeat investigate -> plan -> approve -> execute -> verify until recovery or a stop condition.

    investigate(incident_id, prior_attempts) runs a fresh agent investigation; it is called for every
    attempt that has no ready transcript (attempt 1 uses first_transcript when given).
    approval_callback is for tests only; product code asks a human on approval_channel each attempt.
    Returns the last attempt's outcome with .attempts, .final_status, .final_reason and .report_paths set.
    """
    if first_transcript is None and investigate is None:
        raise ValueError("run_remediation_loop needs first_transcript or investigate")
    cfg = settings or Settings()
    n = clamp_attempts(max_attempts)
    events = events or EventLog.from_settings(cfg, echo=False)
    emit = _Trail(events, on_event)
    emit.max_attempts = n
    timeline: List[Dict[str, Any]] = []
    attempts: List[PipelineOutcome] = []
    failed: Dict[str, int] = {}
    prior: List[Dict[str, Any]] = []
    t = first_transcript
    incident_id = t.incident_id if t is not None else None

    def segment(start: int) -> None:
        timeline.extend(r for r in events.records[start:] if r.get("event") not in ("TOOL_CALL", "MODEL_NOTE"))

    for attempt in range(1, n + 1):
        emit.attempt = attempt
        if attempt > 1:
            mark = len(events.records)
            reasons = " and ".join(kill_switch_reasons(cfg))
            emit("KILL_SWITCH", f"between_attempts: {'ENGAGED, ' + reasons if reasons else 'clear'}",
                 checkpoint="between_attempts", engaged=bool(reasons), reason=reasons or None, action_id=None)
            segment(mark)
            if reasons:
                attempts.append(PipelineOutcome(BLOCKED_BY_KILL_SWITCH, reason="emergency kill switch is engaged; "
                                                "no further attempt was started", attempt=attempt, transcript=t))
                break
            mark = len(events.records)
            try:
                t = investigate(incident_id, list(prior))
            except Exception as e:
                segment(mark)
                attempts.append(PipelineOutcome("REINVESTIGATION_FAILED", reason=f"re-investigation failed: {e}",
                                                attempt=attempt, transcript=t))
                break
            segment(mark)
        elif t is None:
            t = investigate(None, [])
        incident_id = t.incident_id
        events.bind(incident_id)
        if n > 1:
            _save_attempt(t, cfg, attempt, list(prior))
        mark = len(events.records)
        o = run_attempt(t, cfg, emit, approval_callback, approval_channel, dry_run, ctx, backend, sleep, clock,
                        open_browser, attempt=attempt, failed_signatures=failed)
        segment(mark)
        attempts.append(o)
        if o.status in RETRY_STATUSES and attempt < n:
            failed[action_signature(o.action)] = attempt
            prior.append(prior_context(o))
            continue
        break

    final = attempts[-1]
    final.attempts = attempts
    final.final_status, final.final_reason = final_status(final, len(attempts), n)
    if final.escalated:
        mark = len(events.records)
        emit("ESCALATION", f"{final.final_status}: {final.final_reason}", status=final.status,
             final_status=final.final_status, reason=final.final_reason, attempts=len(attempts),
             action_id=final.action.action_id if final.action else None)
        segment(mark)
    final.timeline = timeline
    finalize_report(t, cfg, final, events, max_attempts=n)
    return final


def attempt_transcript_path(cfg: Settings, incident_id: str, attempt: int) -> Path:
    return cfg.resolve_path(cfg.report_output_dir) / incident_id / "attempts" / f"attempt-{attempt}.transcript.json"
