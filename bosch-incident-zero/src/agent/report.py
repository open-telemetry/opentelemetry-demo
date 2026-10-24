"""Map the agent's diagnosis onto the incident report schema and validate it.

The schema used here is the repository's config/incident_schema.json. The organisers' template
schema takes precedence once it is available; only build_report() needs to change.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

from .transcript import Transcript, utc_now

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "incident_schema.json"
_CONFIDENCE_SCORE = {"high": 0.85, "medium": 0.6, "low": 0.3}


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


def validate_report(report: Dict[str, Any], schema_path: Optional[Path] = None) -> Tuple[bool, List[str]]:
    schema = json.loads((schema_path or SCHEMA_PATH).read_text())
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in validator.iter_errors(report)]
    return not errors, errors
