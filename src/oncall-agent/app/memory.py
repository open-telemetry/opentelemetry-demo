from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any

from app.approval import IncidentRecord
from app.config import DATA_DIR, MEMORY_SQLITE_PATH

logger = logging.getLogger("oncall-agent.memory")


def init_memory_db(db_path: Path | None = None) -> None:
    path = db_path or MEMORY_SQLITE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                fingerprint TEXT,
                symptoms TEXT,
                component TEXT,
                category TEXT,
                diagnosis_summary TEXT,
                runbook_id TEXT,
                outcome TEXT,
                steps_used INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        cols = [col[1] for col in conn.execute("PRAGMA table_info(incidents)").fetchall()]
        if "steps_used" not in cols:
            conn.execute("ALTER TABLE incidents ADD COLUMN steps_used INTEGER DEFAULT 0")
        conn.commit()


def _tokenize(text: str) -> set[str]:
    # Match alphanumeric token words for lexical matching
    return set(re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower()))


def save_to_memory(
    rec: IncidentRecord,
    steps_used: int = 0,
    db_path: Path | None = None,
) -> None:
    path = db_path or MEMORY_SQLITE_PATH
    init_memory_db(path)

    # Determine outcome
    outcome_map = {
        "RESOLVED": "fixed",
        "ROLLED_BACK": "not_fixed",
        "ESCALATED": "escalated",
        "REJECTED": "not_fixed",
    }
    outcome = outcome_map.get(rec.state.value, "unknown")

    diag = rec.diagnosis or {}
    component = diag.get("component") or ""
    category = diag.get("cause_category") or ""
    diagnosis_summary = diag.get("cause_description") or ""

    runbook_id = ""
    if rec.execution_results:
        # Check first executed runbook if recorded
        first_res = rec.execution_results[0]
        runbook_id = first_res.get("runbook_id") or first_res.get("action") or ""
    elif rec.proposals:
        runbook_id = rec.proposals[0].get("runbook_id") or ""

    symptoms_str = json.dumps(rec.symptoms)

    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                INSERT INTO incidents (
                    incident_id, fingerprint, symptoms, component, category,
                    diagnosis_summary, runbook_id, outcome, steps_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    fingerprint=excluded.fingerprint,
                    symptoms=excluded.symptoms,
                    component=excluded.component,
                    category=excluded.category,
                    diagnosis_summary=excluded.diagnosis_summary,
                    runbook_id=excluded.runbook_id,
                    outcome=excluded.outcome,
                    steps_used=excluded.steps_used,
                    created_at=excluded.created_at
                """,
                (
                    rec.incident_id,
                    rec.fingerprint,
                    symptoms_str,
                    component,
                    category,
                    diagnosis_summary,
                    runbook_id,
                    outcome,
                    steps_used,
                    now,
                ),
            )
            conn.commit()
        logger.info("Saved incident %s to memory (outcome: %s, steps: %d)", rec.incident_id, outcome, steps_used)
    except Exception as e:
        logger.error("Failed to save incident %s to memory: %s", rec.incident_id, e)


def search_memory(
    symptom_summary: str,
    fingerprint: str = "",
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    path = db_path or MEMORY_SQLITE_PATH
    init_memory_db(path)

    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT incident_id, fingerprint, symptoms, component, category, diagnosis_summary, runbook_id, outcome, steps_used, created_at FROM incidents"
            ).fetchall()
    except Exception as e:
        logger.error("Error querying incident memory: %s", e)
        return []

    if not rows:
        return []

    query_tokens = _tokenize(f"{fingerprint} {symptom_summary}")
    scored: list[tuple[float, dict[str, Any]]] = []

    for r in rows:
        record = dict(r)
        # Exact fingerprint match gets a strong similarity baseline
        exact_fp = fingerprint and record.get("fingerprint") == fingerprint

        doc_text = " ".join([
            str(record.get("fingerprint") or ""),
            str(record.get("symptoms") or ""),
            str(record.get("component") or ""),
            str(record.get("category") or ""),
            str(record.get("diagnosis_summary") or ""),
        ])
        doc_tokens = _tokenize(doc_text)
        if not doc_tokens:
            continue

        overlap = len(query_tokens & doc_tokens)
        sim = overlap / (len(query_tokens) + len(doc_tokens) - overlap) if (len(query_tokens) + len(doc_tokens) - overlap) > 0 else 0.0

        if exact_fp:
            sim = max(sim, 0.85)

        # Deprioritize fixes that previously failed (outcome != 'fixed')
        if record.get("outcome") != "fixed":
            sim *= 0.75

        if sim > 0.05:
            record["similarity"] = round(sim, 2)
            scored.append((sim, record))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:3]]


def find_memory_assist(
    fingerprint: str,
    symptom_summary: str,
    current_steps: int = 0,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    matches = search_memory(symptom_summary, fingerprint=fingerprint, db_path=db_path)
    if not matches:
        return None

    top = matches[0]
    if top.get("similarity", 0) >= 0.60 and top.get("outcome") == "fixed":
        prev_steps = top.get("steps_used", 0)
        steps_saved = max(0, prev_steps - current_steps) if prev_steps > 0 else 0
        return {
            "matched_incident": top.get("incident_id"),
            "similarity": top.get("similarity"),
            "prev_steps": prev_steps,
            "current_steps": current_steps,
            "steps_saved": steps_saved,
            "recommended_runbook": top.get("runbook_id"),
            "component": top.get("component"),
        }
    return None


def reindex_from_reports(
    reports_dir: Path | None = None,
    db_path: Path | None = None,
) -> int:
    r_dir = reports_dir or (DATA_DIR / "reports")
    path = db_path or MEMORY_SQLITE_PATH
    init_memory_db(path)

    if not r_dir.exists():
        return 0

    count = 0
    for f in r_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            inc_id = data.get("incident_id")
            if not inc_id:
                continue

            status = data.get("status", "")
            outcome_map = {
                "resolved": "fixed",
                "rolled_back": "not_fixed",
                "escalated": "escalated",
                "rejected": "not_fixed",
            }
            outcome = outcome_map.get(status, "unknown")

            root_cause = data.get("root_cause") or {}
            component = root_cause.get("component") or ""
            category = root_cause.get("category") or ""
            diag_desc = root_cause.get("description") or ""

            runbook_id = ""
            actions = data.get("actions") or []
            if actions:
                runbook_id = actions[0].get("runbook_id") or actions[0].get("action") or ""

            symptoms_str = json.dumps(data.get("symptoms") or [])
            created_at = data.get("detected_at") or datetime.now(timezone.utc).isoformat()

            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    INSERT INTO incidents (
                        incident_id, fingerprint, symptoms, component, category,
                        diagnosis_summary, runbook_id, outcome, steps_used, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(incident_id) DO UPDATE SET
                        fingerprint=excluded.fingerprint,
                        symptoms=excluded.symptoms,
                        component=excluded.component,
                        category=excluded.category,
                        diagnosis_summary=excluded.diagnosis_summary,
                        runbook_id=excluded.runbook_id,
                        outcome=excluded.outcome,
                        created_at=excluded.created_at
                    """,
                    (
                        inc_id,
                        f"{component}:{category}",
                        symptoms_str,
                        component,
                        category,
                        diag_desc,
                        runbook_id,
                        outcome,
                        len(data.get("timeline") or []),
                        created_at,
                    ),
                )
                conn.commit()
            count += 1
        except Exception as e:
            logger.warning("Error reindexing report %s: %s", f, e)

    logger.info("Reindexed %d incident reports into memory", count)
    return count
