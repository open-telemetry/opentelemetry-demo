from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from oncall.contracts import Evidence, Fact, Signal
from oncall.schema import FAULT_CLASSES, Diagnosis


class EvidenceLedger:
    def __init__(self) -> None:
        self._items: dict[str, Evidence] = {}
        self._lock = threading.Lock()

    def add(self, tool: str, query: str, fact: Fact) -> Evidence:
        with self._lock:
            evidence_id = f"E-{len(self._items) + 1:03d}"
            evidence = Evidence(
                id=evidence_id,
                signal=fact.signal,
                tool=tool,
                query=query,
                ts=datetime.now(timezone.utc).isoformat(),
                summary=fact.summary,
                data=fact.data,
            )
            self._items[evidence_id] = evidence
            return evidence

    def get(self, evidence_id: str) -> Evidence | None:
        with self._lock:
            return self._items.get(evidence_id)

    def has(self, evidence_id: str) -> bool:
        return self.get(evidence_id) is not None

    def all(self) -> list[Evidence]:
        with self._lock:
            return list(self._items.values())

    def signals_for(self, ids: list[str]) -> set[Signal]:
        with self._lock:
            return {self._items[item].signal for item in ids if item in self._items}

    def dump_jsonl(self, path: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as output:
            for evidence in self.all():
                output.write(json.dumps(evidence.model_dump(), default=str) + "\n")

    def enforce(self, diagnosis: Diagnosis) -> Diagnosis:
        """Strip evidence IDs the tools never returned; invented or missing evidence forces escalation."""
        cited = list(dict.fromkeys(diagnosis.evidence_ids))
        valid = [item for item in cited if self.has(item)]
        invented = len(cited) - len(valid)
        result = diagnosis.model_copy(update={"evidence_ids": valid})
        if result.fault_class not in FAULT_CLASSES:
            result.fault_class = "unknown"
        result.confidence = min(max(result.confidence, 0.0), 1.0)
        if invented:
            result.next_steps = [*result.next_steps, f"{invented} cited evidence ID(s) did not exist and were removed"]
        if invented or not valid:
            result.escalate = True
            result.confidence = min(result.confidence, 0.3)
        return result
