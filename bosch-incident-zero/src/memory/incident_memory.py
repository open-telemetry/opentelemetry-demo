"""Incident memory: find past incidents that look like the current one.

A HINT for the operator only. It never counts as evidence, is never cited, and never changes confidence.
It reads only the agent's own outputs (incident_output/<id>/transcript.json, else report.json, including
per-case folders inside eval-<stamp>/). It never opens the harness's results.json, results.jsonl or
summary.json, which hold the evaluator-only expected answers, and flag data is stripped from what it reads.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from ..agent.tools import TOPOLOGY, strip_flag_data

_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "has", "have", "not", "but",
    "its", "into", "over", "above", "below", "than", "then", "when", "while", "after", "before", "because",
    "calls", "call", "service", "services", "rate", "requests", "request", "incident",
}
_SERVICES: Set[str] = set(TOPOLOGY) | {d for deps in TOPOLOGY.values() for d in deps}
# Lowercase words of 3+ letters, digits or hyphens (service names such as product-catalog stay whole).
_WORD = re.compile(r"[a-z0-9][a-z0-9-]{2,}")


def keywords(text: str) -> Set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOPWORDS}


def services_in(text: str) -> Set[str]:
    words = set(_WORD.findall((text or "").lower()))
    return {s for s in _SERVICES if s in words}


@dataclass
class PastIncident:
    incident_id: str
    service: str
    category: str
    confidence: str
    escalated: bool
    summary: str
    keywords: Set[str] = field(default_factory=set)
    services: Set[str] = field(default_factory=set)


def _load(run_dir: Path) -> Optional[PastIncident]:
    t_path, r_path = run_dir / "transcript.json", run_dir / "report.json"
    try:
        if t_path.is_file():
            t = strip_flag_data(json.loads(t_path.read_text(encoding="utf-8")))
            diag = t.get("diagnosis") or {}
            root = diag.get("root_cause") or {}
            gate = t.get("gate") or {}
            alert, summary = str(t.get("alert") or ""), str(root.get("summary") or "")
            return PastIncident(
                incident_id=str(t.get("incident_id") or run_dir.name), service=str(root.get("service") or ""),
                category=str(root.get("category") or ""), confidence=str(gate.get("final_confidence") or "low"),
                escalated=bool(gate.get("escalate", True)), summary=summary[:300],
                keywords=keywords(f"{alert} {summary}"),
                services=services_in(f"{alert} {summary}") | ({root["service"]} if root.get("service") else set()))
        if r_path.is_file():
            r = strip_flag_data(json.loads(r_path.read_text(encoding="utf-8")))
            summary = str(r.get("root_cause_summary") or "")
            service = str(r.get("target_service") or "")
            return PastIncident(
                incident_id=str(r.get("incident_id") or run_dir.name), service=service, category="",
                confidence="unknown", escalated=str(r.get("status", "")).upper() == "ESCALATED",
                summary=summary[:300], keywords=keywords(summary),
                services=services_in(summary) | ({service} if service else set()))
    except (OSError, ValueError, AttributeError):
        return None
    return None


def _run_dirs(output_dir: Path) -> Iterable[Path]:
    if not output_dir.is_dir():
        return
    for d in sorted(output_dir.iterdir()):
        if not d.is_dir():
            continue
        if d.name.startswith("eval-"):
            yield from (c for c in sorted(d.iterdir()) if c.is_dir())
        else:
            yield d


class IncidentMemory:
    def __init__(self, incidents: List[PastIncident]) -> None:
        self.incidents = incidents

    @classmethod
    def from_dir(cls, output_dir: Path | str) -> "IncidentMemory":
        loaded = (_load(d) for d in _run_dirs(Path(output_dir)))
        return cls([p for p in loaded if p is not None])

    def find_similar(self, alert: str, summary: str = "", limit: int = 3,
                     exclude: Optional[str] = None) -> List[Dict[str, Any]]:
        """Past incidents ranked by shared services (weight 2) and shared keywords. Hint only."""
        text = f"{alert} {summary}"
        kws, svcs = keywords(text), services_in(text)
        scored = []
        for p in self.incidents:
            if p.incident_id == exclude:
                continue
            shared_svcs, shared_kws = svcs & p.services, (kws & p.keywords) - svcs
            score = 2 * len(shared_svcs) + len(shared_kws)
            if score:
                scored.append((score, p, sorted(shared_svcs), sorted(shared_kws)))
        scored.sort(key=lambda s: (-s[0], s[1].incident_id))
        return [{"incident_id": p.incident_id, "diagnosed_as": f"{p.service or '?'}/{p.category or '?'}",
                 "confidence": p.confidence, "escalated": p.escalated, "score": score,
                 "matched_services": ms, "matched_keywords": mk, "hint_only": True}
                for score, p, ms, mk in scored[:limit]]


def format_hints(hints: List[Dict[str, Any]]) -> str:
    if not hints:
        return "Similar past incidents: none found."
    lines = ["Similar past incidents (hint only; not evidence, does not affect confidence):"]
    for h in hints:
        tag = " (escalated)" if h["escalated"] else ""
        lines.append(f"  - {h['incident_id']}: diagnosed as {h['diagnosed_as']}, confidence {h['confidence']}"
                     f"{tag}; shared: {', '.join(h['matched_services'] + h['matched_keywords'])}")
    return "\n".join(lines)
