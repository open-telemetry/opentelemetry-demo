"""Stored record of one incident run: tool calls, results, findings and the final verdict."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class EvidenceIndex:
    """Everything that may be cited, built only from stored tool results."""
    trace_ids: Set[str] = field(default_factory=set)
    span_refs: Set[str] = field(default_factory=set)
    logs: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, List[Any]] = field(default_factory=dict)
    containers: Dict[str, List[Any]] = field(default_factory=dict)
    # (caller, dependency) pairs where a failing client call never reached the dependency
    unreached: Set[Tuple[str, str]] = field(default_factory=set)


    def all_text(self) -> str:
        return "\n".join(self.logs.values())


@dataclass
class Transcript:
    incident_id: str
    alert: str
    started_at: str = field(default_factory=utc_now)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    model_notes: List[str] = field(default_factory=list)
    findings: str = ""
    step_cap_hit: bool = False
    diagnosis_attempts: List[Dict[str, Any]] = field(default_factory=list)
    diagnosis: Optional[Dict[str, Any]] = None
    citations: List[Dict[str, Any]] = field(default_factory=list)
    gate: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None
    report_schema_valid: Optional[bool] = None
    report_schema_errors: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    finished_at: Optional[str] = None

    def record_tool(self, name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> None:
        self.tool_calls.append({"n": len(self.tool_calls) + 1, "at": utc_now(), "tool": name,
                                "arguments": arguments, "result": result})

    def evidence_index(self) -> EvidenceIndex:
        idx = EvidenceIndex()
        for call in self.tool_calls:
            for ev in call["result"].get("evidence", []) or []:
                ref = str(ev.get("ref", ""))
                kind = ev.get("kind")
                if kind == "trace":
                    if ev.get("reached") is False and ev.get("caller") and ev.get("dependency"):
                        idx.unreached.add((ev["caller"], ev["dependency"]))

                    if ref.startswith("span:"):
                        idx.span_refs.add(ref.lower())
                        idx.trace_ids.add(ref.split(":")[1].lower())
                    else:
                        idx.trace_ids.add(ref.lower())
                elif kind == "log":
                    idx.logs[ref] = str(ev.get("text", ""))
                elif kind == "metric":
                    idx.metrics.setdefault(ref, []).append(ev.get("value"))
                elif kind == "container":
                    idx.containers.setdefault(ref, []).append(ev.get("value"))
        return idx

    def compact_for_prompt(self, max_chars: int = 60000) -> str:
        """Tool calls and results as compact JSON for the diagnosis phase."""
        rows = [{"n": c["n"], "tool": c["tool"], "arguments": c["arguments"], "result": c["result"]}
                for c in self.tool_calls]
        text = json.dumps(rows, default=str, separators=(",", ":"))
        if len(text) > max_chars:
            text = text[:max_chars] + "...(truncated)"
        return text

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    def save(self, out_dir: Path) -> Path:
        run_dir = Path(out_dir) / self.incident_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "transcript.json").write_text(json.dumps(self.to_dict(), indent=2, default=str))
        if self.report is not None:
            (run_dir / "report.json").write_text(json.dumps(self.report, indent=2, default=str))
        return run_dir
