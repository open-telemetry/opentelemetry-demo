from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


EVENT_TYPES = {"alert", "tool_call", "tool_result", "agent_step", "verifier", "diagnosis", "error"}


class EventLog:
    def __init__(self, run_id: str, runs_dir: str = "runs") -> None:
        self.path = Path(runs_dir) / run_id / "events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event type: {event_type}")
        event = {"ts": datetime.now(timezone.utc).isoformat(), "type": event_type, "payload": payload}
        with self._lock, self.path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(event, default=str) + "\n")
