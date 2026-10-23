from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
from typing import Any

from app.config import DATA_DIR


class EvidenceLedger:
    def __init__(self, incident_id: str, storage_dir: Path | None = None) -> None:
        self.incident_id = incident_id
        base_dir = storage_dir or DATA_DIR
        self.incident_dir = base_dir / "incidents" / incident_id
        self.filepath = self.incident_dir / "evidence.jsonl"
        self._lock = threading.Lock()
        self._evidence_records: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            self._evidence_records.append(rec)
                            self._by_id[rec["evidence_id"]] = rec
            except Exception:
                pass

    def record_evidence(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        raw_result: str,
        ev_type: str,
    ) -> str:
        with self._lock:
            next_idx = len(self._evidence_records) + 1
            eid = f"E{next_idx}"
            record = {
                "evidence_id": eid,
                "type": ev_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_name": tool_name,
                "tool_args": tool_args,
                "raw_result": raw_result,
                "compact_rendering": raw_result[:500],
            }
            self._evidence_records.append(record)
            self._by_id[eid] = record

            try:
                self.incident_dir.mkdir(parents=True, exist_ok=True)
                with open(self.filepath, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, separators=(",", ":")) + "\n")
            except Exception:
                pass

            return eid

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._by_id.get(evidence_id)

    def get_all_evidence(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._evidence_records)

    def verify_citation(self, evidence_id: str, ref: str) -> tuple[bool, str]:
        rec = self.get_evidence(evidence_id)
        if not rec:
            return False, f"Evidence citation '{evidence_id}' does not exist in ledger"

        if not ref or not isinstance(ref, str) or not ref.strip():
            return False, f"Empty reference string cited for evidence '{evidence_id}'"

        ref_clean = ref.strip()
        raw_text = rec.get("raw_result", "")
        raw_lower = raw_text.lower()
        ref_lower = ref_clean.lower()

        # 1. Direct substring match
        if ref_lower in raw_lower:
            return True, ""

        # 2. Check 32-character hexadecimal trace ID if present in ref
        trace_id_match = re.search(r"\b([0-9a-fA-F]{32})\b", ref_clean)
        if trace_id_match and trace_id_match.group(1).lower() in raw_lower:
            return True, ""

        # 3. Numeric metric value with +/- 5% tolerance
        # Extract numbers like 100, 100.0, 50, 420.5 from ref
        ref_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", ref_clean)
        if ref_numbers:
            raw_numbers = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", raw_text)]
            for r_num_str in ref_numbers:
                try:
                    target_val = float(r_num_str)
                    matched_num = False
                    for val in raw_numbers:
                        if target_val == 0.0 and val == 0.0:
                            matched_num = True
                            break
                        if target_val != 0.0 and abs(val - target_val) / abs(target_val) <= 0.05:
                            matched_num = True
                            break
                    if matched_num:
                        # Verify associated service or metric keyword also appears
                        words = [w for w in re.findall(r"[a-zA-Z_\-]+", ref_lower) if len(w) > 3]
                        if not words or any(w in raw_lower for w in words):
                            return True, ""
                except ValueError:
                    pass

        # 4. Multi-word phrase matching with partial token overlap
        tokens = [w for w in re.findall(r"[a-zA-Z0-9_\-]+", ref_lower) if len(w) >= 3]
        if len(tokens) >= 3:
            matched_tokens = sum(1 for tok in tokens if tok in raw_lower)
            if matched_tokens / len(tokens) >= 0.75:
                return True, ""

        return False, f"Ref '{ref_clean}' could not be substantiated in evidence '{evidence_id}' (invented evidence)"
