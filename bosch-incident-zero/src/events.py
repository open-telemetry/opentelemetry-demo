"""Run events: one append-only JSONL contract shared by the agent, the safety pipeline, the CLI and the chat UI.

Each line of the audit log is {ts, incident_id, event, summary, data}. The same event is echoed to the
terminal as one timestamped line and appended to incident_output/<incident_id>/run.log.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Tuple

EVENTS = frozenset({
    "ALERT_RECEIVED", "TOOL_CALL", "MODEL_NOTE", "DIAGNOSIS", "GATE",
    "PLAN", "APPROVAL_REQUESTED", "APPROVAL_DECISION",
    "ACTION_EXECUTED", "DRY_RUN", "ACTION_REFUSED", "KILL_SWITCH",
    "VERIFICATION", "ROLLBACK", "ESCALATION", "REPORT_WRITTEN",
    "UI_EVENT", "ERROR",
})

# Key names that hold credentials, e.g. api_key, LLM_API_KEY, x-api-key, csrf_token, Authorization.
# Anchored at the end so counters such as prompt_tokens are kept.
_SECRET_KEY = re.compile(r"(?:^|_)(?:api_?key|token|secret|password|passwd|authorization|cookie)$", re.IGNORECASE)
# Credential-looking values: provider keys such as sk-or-v1-..., and "Bearer <token>" headers.
_SECRET_VALUE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_REDACTED = "[REDACTED]"
_write_lock = threading.Lock()


def utc_now_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def redact_text(text: Any) -> str:
    return _SECRET_VALUE.sub(_REDACTED, "" if text is None else str(text))


def _drop_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: (_REDACTED if isinstance(k, str) and _SECRET_KEY.search(k.replace("-", "_")) else _drop_secrets(v))
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_drop_secrets(x) for x in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def scrub(data: Any) -> Any:
    """Remove flag-related entries and credentials from event data."""
    from .agent.tools import strip_flag_data  # imported lazily: src.agent imports this module

    return _drop_secrets(strip_flag_data(data))


def format_line(record: Dict[str, Any]) -> str:
    ts = record.get("ts", "")
    clock = ts[11:23] + "Z" if len(ts) >= 23 else ts
    return f"{clock} {record.get('event', ''):<18} {record.get('summary', '')}"


def _append(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


class EventLog:
    """Emits run events to the audit log, the per-incident run.log and (unless quiet) the terminal.

    audit_log_path=None keeps events in memory only, which is what most unit tests want.
    """

    def __init__(
        self,
        audit_log_path: Optional[Path | str] = None,
        incident_id: Optional[str] = None,
        run_log_dir: Optional[Path | str] = None,
        echo: bool = True,
        stream: Optional[TextIO] = None,
    ) -> None:
        self.audit_log_path = Path(audit_log_path) if audit_log_path else None
        self.incident_id = incident_id
        self.run_log_dir = Path(run_log_dir) if run_log_dir else None
        self.echo = echo
        self.stream = stream
        self.records: List[Dict[str, Any]] = []

    @classmethod
    def from_settings(cls, settings: Any, echo: bool = True, incident_id: Optional[str] = None,
                      stream: Optional[TextIO] = None) -> "EventLog":
        def resolve(p: str) -> Path:
            path = Path(p)
            return path if path.is_absolute() else settings.root_dir / path

        return cls(resolve(settings.audit_log_path), incident_id=incident_id,
                   run_log_dir=resolve(settings.report_output_dir), echo=echo, stream=stream)

    @property
    def run_log_path(self) -> Optional[Path]:
        if self.run_log_dir is None or not self.incident_id:
            return None
        return self.run_log_dir / self.incident_id / "run.log"

    def bind(self, incident_id: str) -> None:
        self.incident_id = incident_id

    def emit(self, event: str, summary: str, data: Optional[Dict[str, Any]] = None,
             incident_id: Optional[str] = None) -> Dict[str, Any]:
        if event not in EVENTS:
            raise ValueError(f"unknown event {event!r}; add it to src.events.EVENTS first")
        record = {
            "ts": utc_now_ms(),
            "incident_id": incident_id or self.incident_id,
            "event": event,
            "summary": redact_text(summary),
            "data": scrub(data or {}),
        }
        line = format_line(record)
        if self.audit_log_path is not None:
            _append(self.audit_log_path, json.dumps(record, default=str))
        if self.run_log_path is not None:
            _append(self.run_log_path, line)
        if self.echo:
            print(line, file=self.stream or sys.stdout, flush=True)
        self.records.append(record)
        return record


def read_events(audit_log_path: Path | str, incident_id: Optional[str] = None,
                after_line: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    """Return contract records after line number `after_line` and the new line count, for polling readers.

    Lines from the older audit format (no "ts"/"event") and malformed lines are skipped.
    """
    path = Path(audit_log_path)
    if not path.exists():
        return [], 0
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for raw in lines[after_line:]:
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict) or "ts" not in rec or "event" not in rec:
            continue
        if incident_id and rec.get("incident_id") != incident_id:
            continue
        records.append(rec)
    return records, len(lines)
