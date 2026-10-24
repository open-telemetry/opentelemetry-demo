"""Run log implementation for recording all LLM calls, tool calls, and decisions."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

try:
    from oncall.models import Evidence
except ImportError:
    # Fallback definition matching docs/hackathon/interfaces.md
    class Evidence(TypedDict, total=False):
        id: str
        text: str
        ts: str | None


VALID_EVENTS = {
    "alert",
    "llm_call",
    "tool_call",
    "tool_result",
    "decision",
    "action",
    "error",
    "finish",
}


class RunLog:
    """Append-only JSONL run log tracking agent investigation lifecycle."""

    def __init__(self, run_id: str | None = None, runs_dir: str = "runs") -> None:
        if run_id is None:
            ts_prefix = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            run_id = f"{ts_prefix}_{uuid.uuid4().hex[:6]}"

        self.run_id: str = run_id
        self.runs_dir: Path = Path(runs_dir)
        self.path: Path = self.runs_dir / f"{self.run_id}.jsonl"

        # Ensure runs directory exists
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **data: Any) -> None:
        """Append an event to the run log with timestamp.

        Flushes immediately so events are written even if the process exits.
        """
        ts = data.pop("ts", None) or datetime.now(UTC).isoformat()
        record = {"event": event, "ts": ts, **data}

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

    def events(self, event: str | None = None) -> list[dict[str, Any]]:
        """Return all logged events, optionally filtered by event type."""
        if not self.path.exists():
            return []

        records: list[dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if event is None or rec.get("event") == event:
                        records.append(rec)
                except json.JSONDecodeError:
                    continue
        return records

    def evidence_index(self) -> dict[str, Evidence]:
        """Extract every Evidence item from every tool_result event, keyed by id."""
        index: dict[str, Evidence] = {}
        for entry in self.events(event="tool_result"):
            ev_list = entry.get("evidence")
            if ev_list is None and isinstance(entry.get("result"), dict):
                ev_list = entry["result"].get("evidence")

            if not isinstance(ev_list, list):
                continue

            for item in ev_list:
                if isinstance(item, dict):
                    ev_id = item.get("id") or item.get("ref")
                    if ev_id:
                        index[str(ev_id)] = item
        return index

    def token_usage(self) -> dict[str, int]:
        """Aggregate token usage across all llm_call events."""
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        calls = 0

        for entry in self.events(event="llm_call"):
            calls += 1
            usage = entry.get("usage")
            if isinstance(usage, dict):
                p = usage.get("prompt_tokens", 0) or 0
                c = (
                    usage.get("completion_tokens", 0)
                    or usage.get("output_tokens", 0)
                    or 0
                )
                t = (
                    usage.get("total_tokens", 0)
                    or (p + c)
                    or entry.get("total_tokens", 0)
                    or 0
                )
            else:
                p = entry.get("prompt_tokens", 0) or entry.get("input_tokens", 0) or 0
                c = (
                    entry.get("completion_tokens", 0)
                    or entry.get("output_tokens", 0)
                    or 0
                )
                t = entry.get("total_tokens", 0) or (p + c)

            prompt_tokens += int(p)
            completion_tokens += int(c)
            total_tokens += int(t)

        return {
            "calls": calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
