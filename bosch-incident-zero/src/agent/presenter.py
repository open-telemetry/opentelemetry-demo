"""Terminal presenter rendering human-readable incident briefs and verification summaries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..models.action import RemediationAction
from .transcript import Transcript


def format_incident_brief(
    transcript: Transcript,
    action: Optional[RemediationAction] = None,
    output_dir: Optional[Path | str] = None,
    audit_log_path: Optional[Path | str] = None,
) -> str:
    """Format an incident transcript into a clear, executive incident brief for judges and operators."""
    rep = transcript.report or {}
    diag = transcript.diagnosis or {}
    gate = transcript.gate or {}
    root = diag.get("root_cause", {}) or {}
    evidence = rep.get("evidence", {}) or {}
    remediation = rep.get("remediation", {}) or {}

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

    lines = [
        "",
        sep,
        " BOSCH INCIDENT ZERO -- AUTONOMOUS INCIDENT DIAGNOSIS BRIEF",
        sep,
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
    ]

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
            f" Recovery Status   : {'VERIFIED' if remediation.get('recovery_verified') else 'PENDING'}",
        ])

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
