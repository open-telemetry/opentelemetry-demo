"""Map the agent's diagnosis and action outcome onto the incident report schema and validate it.

The schema used here is the repository's config/incident_schema.json. The organisers' template
schema takes precedence once it is available; only build_report() and attach_action_outcome()
need to change.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

from ..remediation.verifier import NO_DATA, NOT_RECOVERED, NOT_VERIFIED_DRY_RUN, RECOVERED
from .transcript import Transcript, utc_now

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "incident_schema.json"
_CONFIDENCE_SCORE = {"high": 0.85, "medium": 0.6, "low": 0.3}
_OUTCOME_STATUS = {
    RECOVERED: "RESOLVED",
    NOT_VERIFIED_DRY_RUN: "MITIGATION_UNVERIFIED",
    NO_DATA: "UNVERIFIED_ESCALATED",
    NOT_RECOVERED: "MITIGATION_FAILED",
}
_APPROVAL_STATUSES = ("PENDING", "APPROVED", "REJECTED", "BYPASSED", "BLOCKED_BY_KILL_SWITCH")
PREVENTION: Dict[str, List[str]] = {
    "errors_on_operation": [
        "Add an alert on the error rate of {service}'s failing operation so it pages before users notice.",
        "Add a regression test or contract test for the failing operation before the next release.",
        "Gate releases of {service} on error rate in a canary stage.",
    ],
    "latency_without_errors": [
        "Add a p95 latency SLO and alert for {service}.",
        "Set explicit client timeouts and deadlines on calls into {service}.",
        "Load-test the slow operation and profile it before the next release.",
    ],
    "memory_growth": [
        "Alert on {service} memory as a percentage of its container limit.",
        "Profile {service} heap usage under load to find the growth.",
        "Review the container memory limit and the restart policy for {service}.",
    ],
    "cpu_saturation": [
        "Alert on sustained CPU utilisation of {service}.",
        "Review CPU limits and the scaling policy for {service}.",
        "Profile the hot path of {service} under load.",
    ],
    "container_down_or_restarting": [
        "Add liveness and readiness health checks for {service}.",
        "Alert on container restarts and on non-running state for {service}.",
        "Review the exit code and OOM history of {service} before redeploying.",
    ],
    "dependency_unreachable": [
        "Add health checks and an availability alert for {service}.",
        "Make callers of {service} fail fast with timeouts, retries with backoff and a circuit breaker.",
        "Document a runbook for restoring {service}.",
    ],
    "queue_lag": [
        "Alert on consumer lag for the queue feeding {service}.",
        "Review consumer capacity and partitioning for {service}.",
    ],
    "traffic_spike": [
        "Add rate limiting or load shedding in front of {service}.",
        "Review autoscaling thresholds and capacity headroom for {service}.",
    ],
    "unknown": [
        "Root cause not established: keep the incident open and assign a human owner.",
        "Add the missing telemetry identified during this investigation before closing.",
    ],
}


def build_report(transcript: Transcript) -> Dict[str, Any]:
    diag = transcript.diagnosis or {}
    gate = transcript.gate or {}
    root = diag.get("root_cause") or {}
    valid = [c for c in transcript.citations if c["valid"]]
    idx = transcript.evidence_index()

    trace_ids: List[str] = []
    for c in valid:
        if c["kind"] == "trace":
            tid = c["ref"].split(":")[1] if c["ref"].lower().startswith("span:") else c["ref"]
            if tid.lower() not in (t.lower() for t in trace_ids):
                trace_ids.append(tid)
    metrics_summary: Dict[str, Any] = {}
    for item in diag.get("evidence", []) or []:
        if item.get("kind") in ("metric", "container") and any(
                v["ref"] == item.get("ref") for v in valid):
            store = idx.metrics if item["kind"] == "metric" else idx.containers
            metrics_summary[item["ref"]] = store.get(item["ref"], [None])[-1]
    log_excerpts = [idx.logs[c["ref"]] for c in valid if c["kind"] == "log" and c["ref"] in idx.logs]

    escalate = gate.get("escalate", True)
    summary = root.get("summary") or "No root cause established."
    if escalate:
        summary = "ESCALATED TO HUMAN (insufficient evidence for a confident diagnosis). " + summary
    return {
        "incident_id": transcript.incident_id,
        "timestamp": transcript.finished_at or utc_now(),
        "status": "DETECTED" if escalate else "DIAGNOSED",
        "target_service": root.get("service") or "unknown",
        "impacted_services": [s for s in diag.get("impacted_services", []) or [] if s != root.get("service")],
        "severity": diag.get("severity", "MEDIUM"),
        "root_cause_summary": summary,
        "root_cause_category": root.get("category") or "unknown",
        "confidence_score": _CONFIDENCE_SCORE.get(gate.get("final_confidence", "low"), 0.3),
        "evidence": {"trace_ids": trace_ids, "metrics_summary": metrics_summary, "log_excerpts": log_excerpts},
        "remediation": {
            "recommended_action": diag.get("recommended_next_step") or "Escalate to on-call engineer.",
            "requires_approval": True,
            "approval_status": "PENDING",
            "dry_run": True,
            "executed_at": None,
        },
    }


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _plain(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _rollback(action: Any, rollback_result: Any) -> Optional[Dict[str, Any]]:
    rollback = _field(action, "rollback") or (_field(action, "parameters") or {}).get("rollback")
    if not rollback:
        return None
    res = rollback_result.to_dict() if hasattr(rollback_result, "to_dict") else rollback_result
    return {"action_id": _field(rollback, "action_id"), "type": _enum_value(_field(rollback, "action_type")),
            "target": _field(rollback, "target_service"), "description": _field(rollback, "description"),
            "executed_at": _field(rollback, "executed_at"), "result": res or _field(rollback, "execution_result"),
            "ran": bool(res or _field(rollback, "executed_at"))}


def _action_taken(action: Any, verification: Optional[Dict[str, Any]],
                  rollback_result: Any = None) -> Optional[Dict[str, Any]]:
    if action is None:
        return None
    params = _field(action, "parameters") or {}
    return _plain({
        "action_id": _field(action, "action_id"),
        "type": _enum_value(_field(action, "action_type")),
        "target": _field(action, "target_service"),
        "reason": _field(action, "reason") or _field(action, "description"),
        "parameters": params,
        "dry_run": bool(_field(action, "dry_run", True)),
        "backend": _field(action, "backend") or params.get("backend"),
        "approval_status": _enum_value(_field(action, "approval_status")),
        "approver": _field(action, "approver") or params.get("approver"),
        "approved_at": _field(action, "approved_at"),
        "approval_channel": _field(action, "approval_channel"),
        "executed_at": _field(action, "executed_at"),
        "result": _field(action, "execution_result"),
        "rollback": _rollback(action, rollback_result),
        "recovery_verified": bool(verification and verification.get("status") == RECOVERED),
    })


def _outcome_status(action: Any, verification: Optional[Dict[str, Any]]) -> str:
    if action is None:
        return "ESCALATED"
    if verification is None:
        return "MITIGATION_UNVERIFIED" if _field(action, "executed_at") else "ESCALATED"
    return _OUTCOME_STATUS.get(verification.get("status"), "MITIGATION_UNVERIFIED")


def prevention_for(category: Optional[str], service: str) -> Dict[str, Any]:
    cat = category if category in PREVENTION else "unknown"
    return {"category": cat, "recommendations": [r.format(service=service) for r in PREVENTION[cat]]}


def attach_action_outcome(report: Dict[str, Any], action: Any, verification: Any,
                          timeline: Optional[List[Dict[str, Any]]], audit_log_path: Any,
                          rollback_result: Any = None) -> Dict[str, Any]:
    """Add the action log, verification and an honest outcome status to a diagnosis report.

    RESOLVED is used only when verification shows recovery. Returns a new dict.
    """
    out = dict(report)
    ver = verification.to_dict() if hasattr(verification, "to_dict") else verification
    ver = _plain(ver) if ver is not None else None
    taken = _action_taken(action, ver, rollback_result)

    out["timeline"] = _plain(list(timeline or []))
    out["action_taken"] = taken
    out["verification"] = ver
    out["prevention"] = prevention_for(out.get("root_cause_category"), out.get("target_service") or "unknown")
    out["audit_log"] = str(audit_log_path) if audit_log_path else None
    out["status"] = _outcome_status(action, ver)

    remediation = dict(out.get("remediation") or {})
    if taken is not None:
        remediation["dry_run"] = taken["dry_run"]
        remediation["executed_at"] = taken["executed_at"]
        remediation["recovery_verified"] = taken["recovery_verified"]
        if taken["action_id"]:
            remediation["action_id"] = taken["action_id"]
        if taken["approval_status"] in _APPROVAL_STATUSES and \
                remediation.get("approval_status") != "BLOCKED_BY_KILL_SWITCH":
            remediation["approval_status"] = taken["approval_status"]
    else:
        remediation["recovery_verified"] = False
    out["remediation"] = remediation
    return out


_STATUS_NOTES = {
    "RESOLVED": "Recovery verified by telemetry.",
    "MITIGATION_UNVERIFIED": "Recovery NOT verified - not claimed as resolved.",
    "MITIGATION_FAILED": "Action taken but telemetry shows no recovery.",
    "UNVERIFIED_ESCALATED": "No usable telemetry after the action - recovery not claimed, escalated to a human.",
    "ESCALATED": "Escalated to a human - no verified fix.",
}


def _md(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (dict, list)):
        return f"`{json.dumps(value, default=str)}`"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_report_markdown(report: Dict[str, Any]) -> str:
    """Render a (possibly enriched) incident report as Markdown, for report.md next to report.json."""
    status = report.get("status", "UNKNOWN")
    rem = report.get("remediation") or {}
    taken = report.get("action_taken")
    ver = report.get("verification")
    ev = report.get("evidence") or {}
    lines = [f"# Incident {report.get('incident_id', 'unknown')}", ""]
    if (taken and taken.get("dry_run")) or (taken is None and rem.get("dry_run") and rem.get("executed_at")):
        lines += ["> **DRY RUN - nothing was changed.**", ""]
    lines += [f"**Status:** {status}" + (f" - {_STATUS_NOTES[status]}" if status in _STATUS_NOTES else ""), "",
              "| Field | Value |", "|---|---|"]
    for label, key in (("Diagnosed at", "timestamp"), ("Target service", "target_service"),
                       ("Severity", "severity"), ("Confidence", "confidence_score"),
                       ("Category", "root_cause_category")):
        lines.append(f"| {label} | {_md(report.get(key))} |")
    lines.append(f"| Impacted services | {_md(', '.join(report.get('impacted_services') or []) or None)} |")
    lines += ["", "## Root cause", "", report.get("root_cause_summary") or "n/a", "", "## Evidence", ""]
    for tid in ev.get("trace_ids") or []:
        lines.append(f"- trace `{tid}`")
    for ref, value in (ev.get("metrics_summary") or {}).items():
        lines.append(f"- `{ref}` = {_md(value)}")
    for log in ev.get("log_excerpts") or []:
        lines.append(f"- log: {_md(log)}")
    if not any(ev.get(k) for k in ("trace_ids", "metrics_summary", "log_excerpts")):
        lines.append("- no validated evidence")

    lines += ["", "## Remediation", "", f"- Recommended: {_md(rem.get('recommended_action'))}",
              f"- Approval: {_md(rem.get('approval_status'))} (required: {_md(rem.get('requires_approval'))})"]
    if taken:
        lines += [f"- Action: {_md(taken.get('type'))} on {_md(taken.get('target'))}"
                  f" ({_md(taken.get('action_id'))})",
                  f"- Reason: {_md(taken.get('reason'))}",
                  f"- Parameters: {_md(taken.get('parameters') or None)}",
                  f"- Approver: {_md(taken.get('approver'))} via {_md(taken.get('approval_channel'))}"
                  f" at {_md(taken.get('approved_at'))}",
                  f"- Backend: {_md(taken.get('backend'))}, dry run: {_md(taken.get('dry_run'))}",
                  f"- Executed at: {_md(taken.get('executed_at'))}, result: {_md(taken.get('result'))}",
                  f"- Rollback: {_md(taken.get('rollback'))}"]
    elif "action_taken" in report:
        lines.append("- No action taken.")

    if report.get("timeline"):
        lines += ["", "## Timeline", "", "| At | Event | Status | Detail |", "|---|---|---|---|"]
        for e in report["timeline"]:
            at = e.get("ts") or e.get("timestamp") or e.get("at")
            detail = e.get("detail") if e.get("detail") is not None else e.get("summary")
            lines.append(f"| {_md(at)} | {_md(e.get('event'))} | {_md(e.get('status'))} | {_md(detail)} |")

    if ver:
        before, after = ver.get("before") or {}, ver.get("after") or {}
        lines += ["", "## Recovery verification", "", f"**{ver.get('status')}** (checked {_md(ver.get('checked_at'))})",
                  "", "| Metric | Before | After |", "|---|---|---|"]
        for label, key in (("Error rate", "error_rate"), ("p95 (ms)", "p95_ms"), ("rps", "rps"),
                           ("Container", "container_state"), ("Health", "container_health"),
                           ("Restarts", "restart_count"), ("Source", "metric_source")):
            lines.append(f"| {label} | {_md(before.get(key))} | {_md(after.get(key))} |")
        lines += [""] + [f"- {r}" for r in ver.get("reasons") or []]
    elif "verification" in report:
        lines += ["", "## Recovery verification", "", "Not verified - no verification was run."]

    prevention = report.get("prevention")
    if prevention:
        lines += ["", "## Prevention", ""] + [f"- {r}" for r in prevention.get("recommendations") or []]
    if report.get("audit_log"):
        lines += ["", f"Audit log: `{report['audit_log']}`"]
    return "\n".join(lines) + "\n"


def write_report_files(report: Dict[str, Any], out_dir: Path, events: Any = None) -> Dict[str, Optional[str]]:
    """Write <out_dir>/<incident_id>/report.json and report.md, scrubbed of flags and credentials."""
    from ..events import scrub

    clean = scrub(_plain(report))
    folder = Path(out_dir) / str(clean.get("incident_id") or "unknown")
    folder.mkdir(parents=True, exist_ok=True)
    json_path, md_path = folder / "report.json", folder / "report.md"
    json_path.write_text(json.dumps(clean, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_report_markdown(clean), encoding="utf-8")
    paths = {"json": str(json_path), "md": str(md_path)}
    if events is not None:
        events.emit("REPORT_WRITTEN", f"{clean.get('status')}: report written to {json_path}", paths,
                    incident_id=clean.get("incident_id"))
    return paths


def validate_report(report: Dict[str, Any], schema_path: Optional[Path] = None) -> Tuple[bool, List[str]]:
    schema = json.loads((schema_path or SCHEMA_PATH).read_text())
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in validator.iter_errors(report)]
    return not errors, errors
