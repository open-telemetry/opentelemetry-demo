"""Incident memory (stretch goal 1): reuse earlier incident reports for a repeat incident.

Only incidents whose action was VERIFIED (system recovered) are trusted as "known good" fixes.
"""
import json

from agent import config

FILE = config.RUNS / "memory.jsonl"


def remember(report: dict):
    rc = report.get("diagnosis", {}).get("root_cause", {})
    row = {"incident_id": report.get("incident_id"), "at": report.get("detected_at"),
           "root_cause_service": rc.get("service"), "fault_type": rc.get("fault_type"),
           "summary": rc.get("summary"), "symptom_services": report.get("alert", {}).get("services", []),
           "action": (report.get("action_plan") or {}).get("action"),
           "outcome": report.get("outcome")}
    with open(FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def similar(services: list, k: int = 3) -> dict:
    try:
        rows = [json.loads(l) for l in FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    except FileNotFoundError:
        return {"matches": [], "note": "no past incidents yet"}
    s = set(services or [])
    scored = []
    for r in rows:
        overlap = s & ({r.get("root_cause_service")} | set(r.get("symptom_services") or []))
        if overlap:
            scored.append((len(overlap) + (1 if r.get("outcome") == "resolved" else 0), r))
    scored.sort(key=lambda x: -x[0])
    return {"matches": [r for _, r in scored[:k]],
            "note": "hints only - confirm with current telemetry before reusing a diagnosis"}
