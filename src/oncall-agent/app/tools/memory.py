from collections import Counter
from pathlib import Path
import re
import sqlite3
from typing import Any

from app.config import MEMORY_SQLITE_PATH


def _init_memory_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
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
                created_at TEXT
            )
        """)
        conn.commit()


def _tokenize(text: str) -> set[str]:
    # Match alphanumeric token words for lexical matching
    return set(re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower()))


def search_incident_memory(symptom_summary: str) -> str:
    if not symptom_summary or not isinstance(symptom_summary, str):
        return "Error: symptom_summary must be a non-empty string."

    db_path = MEMORY_SQLITE_PATH
    try:
        _init_memory_db(db_path)
    except Exception as e:
        return f"Error initializing incident memory database: {e}"

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT incident_id, fingerprint, symptoms, component, category, diagnosis_summary, runbook_id, outcome, created_at FROM incidents"
            ).fetchall()
    except Exception as e:
        return f"Error querying incident memory: {e}"

    if not rows:
        return "No past incidents found in incident memory. (Memory is empty)"

    query_tokens = _tokenize(symptom_summary)
    if not query_tokens:
        return "Warning: symptom_summary contains no indexable terms."

    scored: list[tuple[float, dict[str, Any]]] = []
    for r in rows:
        record = dict(r)
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
        sim = overlap / (len(query_tokens) + len(doc_tokens) - overlap)
        if sim > 0.05:
            scored.append((sim, record))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_matches = scored[:3]

    if not top_matches:
        return f"No similar incidents found in memory for query: '{symptom_summary[:100]}'."

    lines = [
        "Past Incident Memory Matches (NOTE: Memory is a hint only, not direct evidence):",
        "",
    ]
    for sim, rec in top_matches:
        outcome = rec.get("outcome", "unknown")
        outcome_tag = f"[{outcome.upper()}]"
        lines.append(
            f"- Incident {rec.get('incident_id')} (similarity: {sim:.2f}) {outcome_tag}:"
        )
        lines.append(f"  Component: {rec.get('component')}, Category: {rec.get('category')}")
        lines.append(f"  Summary: {rec.get('diagnosis_summary')}")
        lines.append(f"  Runbook Fix: {rec.get('runbook_id', 'none')}")
        lines.append("")

    out = "\n".join(lines).strip()
    return out[:2000]
