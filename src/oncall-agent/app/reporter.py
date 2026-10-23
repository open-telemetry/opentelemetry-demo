from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.approval import IncidentRecord
from app.config import DATA_DIR

logger = logging.getLogger("oncall-agent.reporter")

REPORTS_DIR = DATA_DIR / "reports"
SCHEMA_VERSION = "1.0"


class IncidentReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    incident_id: str
    status: str
    detected_at: str
    resolved_at: str | None = None
    timeline: list[dict[str, Any]] = []
    symptoms: list[dict[str, Any]] = []
    root_cause: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = []
    alternatives_considered: list[str] = []
    actions: list[dict[str, Any]] = []
    verification: dict[str, Any] | None = None
    escalation: dict[str, Any] | None = None
    prevention: list[dict[str, Any]] = []
    memory_assist: dict[str, Any] | None = None
    model: dict[str, str] = {}
    auto_approve_used: bool = False


def build_report(
    rec: IncidentRecord,
    diagnosis: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> IncidentReport:
    now = datetime.now(timezone.utc).isoformat()

    root_cause: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = []
    alternatives: list[str] = []

    diag = diagnosis or rec.diagnosis or {}
    val = validation or rec.validation or {}

    if diag:
        root_cause = {
            "component": diag.get("component"),
            "category": diag.get("cause_category"),
            "description": diag.get("cause_description"),
            "confidence": {
                "model": val.get("model_confidence") or diag.get("confidence"),
                "evidence_score": val.get("evidence_score"),
                "final": val.get("calibrated_confidence") or diag.get("confidence"),
            },
        }
        evidence = diag.get("evidence", [])
        alternatives = diag.get("alternatives_considered", [])

    status_map = {
        "RESOLVED": "resolved",
        "ESCALATED": "escalated",
        "REJECTED": "rejected",
        "ROLLED_BACK": "rolled_back",
    }
    status = status_map.get(rec.state.value, "pending_approval")

    resolved_at: str | None = None
    if rec.state.value in ("RESOLVED", "ESCALATED", "REJECTED", "ROLLED_BACK"):
        resolved_at = now

    prevention_items = rec.prevention
    if not prevention_items and rec.state.value in ("RESOLVED", "ESCALATED"):
        try:
            from app.prevention import generate_prevention, write_prevention_markdown
            prevention_items = generate_prevention(rec)
            write_prevention_markdown(rec.incident_id, prevention_items)
            rec.prevention = prevention_items
        except Exception as e:
            logger.warning("Could not generate prevention items for %s: %s", rec.incident_id, e)

    return IncidentReport(
        incident_id=rec.incident_id,
        status=status,
        detected_at=rec.detected_at,
        resolved_at=resolved_at,
        timeline=rec.timeline,
        symptoms=rec.symptoms,
        root_cause=root_cause,
        evidence=evidence,
        alternatives_considered=alternatives,
        actions=rec.execution_results,
        verification=rec.verification,
        escalation=rec.escalation,
        prevention=prevention_items or [],
        memory_assist=rec.memory_assist,
    )


def validate_report_json(data: dict[str, Any]) -> None:
    import jsonschema
    schema_path = Path(__file__).parent / "schemas" / "incident_report.schema.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text())
        jsonschema.validate(instance=data, schema=schema)


def write_json_report(report: IncidentReport) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{report.incident_id}.json"
    data = json.loads(report.model_dump_json())
    try:
        validate_report_json(data)
    except Exception as e:
        logger.warning("Report schema validation warning for %s: %s", report.incident_id, e)
    path.write_text(json.dumps(data, indent=2))
    logger.info("JSON report written: %s", path)
    return path


def write_markdown_report(report: IncidentReport) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{report.incident_id}.md"

    lines: list[str] = [
        f"# Incident Report: {report.incident_id}",
        "",
        f"**Status:** {report.status.upper()}  ",
        f"**Detected:** {report.detected_at}  ",
        f"**Resolved:** {report.resolved_at or 'N/A'}  ",
        "",
        "## Symptoms",
        "",
    ]
    for s in report.symptoms:
        lines.append(f"- **{s.get('type')}** on `{s.get('service')}`: {s.get('description')}")

    lines += ["", "## Root Cause", ""]
    if report.root_cause:
        rc = report.root_cause
        conf = rc.get("confidence", {})
        lines += [
            f"**Component:** `{rc.get('component')}`  ",
            f"**Category:** `{rc.get('category')}`  ",
            f"**Description:** {rc.get('description')}  ",
            f"**Confidence:** model={conf.get('model', 'N/A')}, evidence={conf.get('evidence_score', 'N/A')}, final={conf.get('final', 'N/A')}  ",
        ]
    else:
        lines.append("_Root cause not determined._")

    lines += ["", "## Evidence", ""]
    for ev in report.evidence:
        lines.append(
            f"- **{ev.get('evidence_id')}** ({ev.get('type')}): `{ev.get('ref', '')[:80]}` — {ev.get('why_it_matters', '')}"
        )

    lines += ["", "## Timeline", ""]
    for t in report.timeline:
        lines.append(f"- `{t.get('ts')}` **{t.get('event')}**: {t.get('detail', '')}")

    if report.actions:
        lines += ["", "## Actions Taken", ""]
        for a in report.actions:
            lines.append(f"- **{a.get('action')}** on `{a.get('params', {})}`: {a.get('result', {})}")

    if report.verification:
        lines += ["", "## Verification", ""]
        v = report.verification
        lines.append(f"- Passed: {v.get('passed')}  ")
        checks = v.get("checks", {})
        for k, val in checks.items():
            lines.append(f"  - {k}: {val}")

    if report.escalation:
        lines += ["", "## Escalation", ""]
        lines.append(f"Reason: {report.escalation.get('reason')}  ")
        lines.append(f"Findings: {report.escalation.get('findings', '')}  ")

    if report.alternatives_considered:
        lines += ["", "## Alternatives Considered", ""]
        for a in report.alternatives_considered:
            lines.append(f"- {a}")

    if report.memory_assist:
        lines += ["", "## Memory Assist", ""]
        ma = report.memory_assist
        lines.append(f"- **Matched Incident:** `{ma.get('matched_incident')}` (similarity: {ma.get('similarity')})")
        lines.append(f"- **Diagnostic Steps Saved:** {ma.get('steps_saved', 0)}")

    if report.prevention:
        lines += ["", "## Prevention Recommendations (Non-Applied)", ""]
        for p in report.prevention:
            valid_str = "Verified" if p.get("validated") else "Unverified"
            lines.append(f"- **[{p.get('type', '').upper()}]** `{p.get('target')}` ({valid_str}): {p.get('rationale')}")

    lines += ["", "---", "*Report generated by AI On-Call Engineer*"]

    path.write_text("\n".join(lines))
    logger.info("Markdown report written: %s", path)
    return path


def write_report(
    rec: IncidentRecord,
    diagnosis: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    report = build_report(rec, diagnosis, validation)
    json_path = write_json_report(report)
    md_path = write_markdown_report(report)
    return json_path, md_path
