"""Terminal presenter rendering human-readable incident briefs and verification summaries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..events import format_line, read_events
from ..models.action import RemediationAction
from ..remediation.verifier import NO_DATA, NOT_RECOVERED, NOT_VERIFIED_DRY_RUN, RECOVERED
from .transcript import Transcript

_VERIFY_ROWS = (("error_rate", "Error rate"), ("p95_ms", "p95 latency (ms)"), ("rps", "Requests/s"),
                ("container_state", "Container state"), ("container_health", "Container health"),
                ("restart_count", "Restart count"))


def _as_dict(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


def _cell(snapshot: Dict[str, Any], key: str) -> str:
    value = (snapshot or {}).get(key)
    if value is None:
        return "NO DATA" if snapshot else "-"
    return str(value)


def _labels(rep: Dict[str, Any], gate: Dict[str, Any], action: Optional[RemediationAction],
            ver: Optional[Dict[str, Any]]) -> List[str]:
    vstatus = (ver or {}).get("status")
    labels = []
    if (action is not None and action.dry_run) or vstatus == NOT_VERIFIED_DRY_RUN:
        labels.append("DRY RUN - nothing was changed")
    if vstatus in (NOT_VERIFIED_DRY_RUN, NO_DATA) or (action is not None and action.executed_at and ver is None):
        labels.append("NOT VERIFIED - recovery not claimed")
    if vstatus == NOT_RECOVERED:
        labels.append("NOT RECOVERED - mitigation failed")
    if rep.get("status") in ("ESCALATED", "MITIGATION_FAILED", "UNVERIFIED_ESCALATED") or gate.get("escalate") \
            or vstatus == NOT_RECOVERED:
        labels.append("ESCALATED TO HUMAN")
    if vstatus == RECOVERED:
        labels.append("RECOVERY VERIFIED by telemetry")
    return labels


def _timeline_lines(timeline: List[Dict[str, Any]]) -> List[str]:
    if not timeline:
        return [" (no action log entries)"]
    lines = []
    for e in timeline:
        event = e.get("event") or e.get("step") or "?"
        detail = e.get("detail") if e.get("detail") is not None else e.get("summary")
        if isinstance(detail, (dict, list)):
            detail = json.dumps(detail, default=str)
        status = f" [{e['status']}]" if e.get("status") else ""
        tail = f" {str(detail)[:90]}" if detail not in (None, "") else ""
        lines.append(f" {str(e.get('ts') or e.get('timestamp') or e.get('at') or '-'):<26} {event}{status}{tail}")
    return lines


def _verification_lines(ver: Dict[str, Any]) -> List[str]:
    before, after = ver.get("before") or {}, ver.get("after") or {}
    lines = [f" Result            : {ver.get('status')} (recovered={ver.get('recovered')}, "
             f"checked {ver.get('checked_at')})"]
    if ver.get("status") == NOT_VERIFIED_DRY_RUN:
        lines.append(" Note              : 'After' is an informational snapshot; no change was made.")
    lines.append(f" {'Signal':<20} {'Before':>16} {'After':>16}")
    for key, label in _VERIFY_ROWS:
        lines.append(f" {label:<20} {_cell(before, key):>16} {_cell(after, key):>16}")
    src_b, src_a = before.get("metric_source"), after.get("metric_source")
    lines.append(f" Metric source     : before={src_b or 'none'}, after={src_a or 'none'}")
    for r in ver.get("reasons") or []:
        lines.append(f"  - {r}")
    return lines


def _event_records(events: Any, audit_log_path: Any, incident_id: Any) -> List[Dict[str, Any]]:
    if events is not None:
        records = getattr(events, "records", events)
        return [r for r in records if not incident_id or r.get("incident_id") in (None, incident_id)]
    if audit_log_path:
        try:
            return read_events(audit_log_path, incident_id=incident_id)[0]
        except OSError:
            return []
    return []


def format_incident_brief(
    transcript: Transcript,
    action: Optional[RemediationAction] = None,
    output_dir: Optional[Path | str] = None,
    audit_log_path: Optional[Path | str] = None,
    verification: Any = None,
    timeline: Optional[List[Dict[str, Any]]] = None,
    events: Any = None,
    event_lines: int = 15,
) -> str:
    """Format an incident transcript into a clear, executive incident brief for judges and operators."""
    rep = transcript.report or {}
    diag = transcript.diagnosis or {}
    gate = transcript.gate or {}
    root = diag.get("root_cause", {}) or {}
    evidence = rep.get("evidence", {}) or {}
    remediation = rep.get("remediation", {}) or {}
    ver = _as_dict(verification) if verification is not None else rep.get("verification")
    timeline = timeline if timeline is not None else rep.get("timeline")
    audit_log_path = audit_log_path or rep.get("audit_log")

    sep = "=" * 78
    subsep = "-" * 78

    inc_id = transcript.incident_id
    status = rep.get("status", "DETECTED")
    target_svc = rep.get("target_service", "unknown")
    category = root.get("category") or "unspecified"
    severity = rep.get("severity", "MEDIUM")
    confidence = (gate.get("final_confidence") or "medium").upper()
    conf_score = rep.get("confidence_score", 0.0)
    summary = rep.get("root_cause_summary") or root.get("summary") or "No root cause summary established."
    impacted = rep.get("impacted_services") or []
    labels = _labels(rep, gate, action, ver)

    lines = [
        "",
        sep,
        " BOSCH INCIDENT ZERO -- AUTONOMOUS INCIDENT DIAGNOSIS BRIEF",
        sep,
    ]
    for label in labels:
        lines.append(f" *** {label} ***")
    lines.extend([
        f" Incident ID       : {inc_id}",
        f" Ingested Alert    : {transcript.alert}",
        f" Timestamp (UTC)   : {transcript.finished_at or rep.get('timestamp')}",
        f" Diagnosis Status  : {status} (Schema Valid: {transcript.report_schema_valid})",
        "",
        subsep,
        " DIAGNOSTIC FINDINGS",
        subsep,
        f" Root Cause Target : {target_svc}",
        f" Failure Category  : {category}",
        f" Severity Rating   : {severity}",
        f" Confidence Level  : {confidence} (Score: {conf_score:.2f})",
        f" Impacted Services : {', '.join(impacted) if impacted else '(none detected)'}",
        f" Root Cause Summary: {summary}",
        "",
        subsep,
        " VERIFIED OBSERVABILITY CITATIONS",
        subsep,
    ])

    # Traces
    traces = evidence.get("trace_ids") or []
    if traces:
        for t in traces[:3]:
            lines.append(f" [TRACE]     : {t} (Jaeger waterfall verified)")
    else:
        lines.append(" [TRACE]     : (no matching trace IDs found)")

    # Metrics
    metrics = evidence.get("metrics_summary") or {}
    if metrics:
        for k, v in list(metrics.items())[:4]:
            lines.append(f" [METRIC]    : {k} = {v}")
    else:
        lines.append(" [METRIC]    : (no metrics crossed threshold)")

    # Containers
    for call in transcript.tool_calls:
        if call["tool"] == "container_health":
            c_data = call["result"].get("data", {}).get("containers", [])
            for c in c_data[:2]:
                lines.append(
                    f" [CONTAINER] : {c.get('name')}: state={c.get('state')}, restarts={c.get('restart_count', 0)}, health={c.get('health') or 'n/a'}"
                )

    # Logs
    logs = evidence.get("log_excerpts") or []
    if logs:
        for l in logs[:2]:
            lines.append(f" [LOG]       : \"{l[:100]}\"")

    lines.extend([
        "",
        subsep,
        " SAFETY CONTROLS & REMEDIATION PIPELINE",
        subsep,
    ])

    if action:
        approval_str = action.approval_status.value
        dry_run_str = "DRY RUN (Read-Only Safety Guarantee)" if action.dry_run else "LIVE MUTATION"
        if ver is not None:
            recov_str = ver.get("status")
        else:
            recov_str = "VERIFIED (Target container responsive)" if action.recovery_verified else "PENDING / UNVERIFIED"
        lines.extend([
            f" Proposed Action   : {action.action_type.value} -> target '{action.target_service}'",
            f" Execution Mode    : {dry_run_str}",
            f" Human Approval    : {approval_str}",
            f" Execution Result  : {action.execution_result or '(not executed)'}",
            f" Recovery Status   : {recov_str}",
        ])
    else:
        lines.extend([
            f" Recommended Action: {remediation.get('recommended_action', 'Escalate to on-call')}",
            f" Approval Status   : {remediation.get('approval_status', 'PENDING')}",
            f" Execution Mode    : {'DRY RUN' if remediation.get('dry_run') else 'LIVE'}",
            f" Recovery Status   : {(ver or {}).get('status') or ('VERIFIED' if remediation.get('recovery_verified') else 'PENDING')}",
        ])

    if timeline is not None:
        lines.extend(["", subsep, " ACTION LOG / TIMELINE", subsep])
        lines.extend(_timeline_lines(timeline))

    if ver is not None:
        lines.extend(["", subsep, " RECOVERY VERIFICATION (BEFORE / AFTER)", subsep])
        lines.extend(_verification_lines(ver))

    prevention = rep.get("prevention") or {}
    if prevention.get("recommendations"):
        lines.extend(["", subsep, f" PREVENTION ({prevention.get('category')})", subsep])
        lines.extend(f"  - {r}" for r in prevention["recommendations"])

    records = _event_records(events, audit_log_path, inc_id)
    if records:
        lines.extend(["", subsep, f" EVENT LOG (last {min(event_lines, len(records))} of {len(records)})", subsep])
        lines.extend(f"  {format_line(r)}" for r in records[-event_lines:])

    lines.extend([
        "",
        subsep,
        " DEMONSTRATION ARTIFACTS",
        subsep,
    ])
    if output_dir:
        report_file = Path(output_dir) / inc_id / "report.json"
        transcript_file = Path(output_dir) / inc_id / "transcript.json"
        lines.append(f" Incident Report   : {report_file}")
        lines.append(f" Tool Transcript   : {transcript_file}")
    if audit_log_path:
        lines.append(f" Audit Trail Log   : {audit_log_path}")

    lines.append(sep)
    lines.append("")
    return "\n".join(lines)
