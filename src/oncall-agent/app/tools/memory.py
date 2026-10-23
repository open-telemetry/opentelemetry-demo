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

    from app.memory import search_memory
    matches = search_memory(symptom_summary)
    if not matches:
        return f"No similar incidents found in memory for query: '{symptom_summary[:100]}'."

    lines = [
        "Past Incident Memory Matches (NOTE: Memory is a hint only, not direct evidence):",
        "",
    ]
    for rec in matches:
        outcome = rec.get("outcome", "unknown")
        sim = rec.get("similarity", 0.0)
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
