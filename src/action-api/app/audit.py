from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any
import uuid

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
AUDIT_FILE = DATA_DIR / "audit.jsonl"
KILLSWITCH_FILE = DATA_DIR / "killswitch.json"


class KillSwitch:
    def __init__(self, filepath: Path = KILLSWITCH_FILE) -> None:
        self._filepath = filepath
        self._lock = threading.Lock()
        self._engaged = False
        self._load()

    def _load(self) -> None:
        if self._filepath.exists():
            try:
                data = json.loads(self._filepath.read_text(encoding="utf-8"))
                self._engaged = bool(data.get("engaged", False))
            except Exception:
                self._engaged = False

    def is_engaged(self) -> bool:
        with self._lock:
            return self._engaged

    def set_engaged(self, engaged: bool) -> bool:
        with self._lock:
            self._engaged = engaged
            try:
                self._filepath.parent.mkdir(parents=True, exist_ok=True)
                self._filepath.write_text(
                    json.dumps({"engaged": self._engaged, "updated_at": datetime.now(timezone.utc).isoformat()}),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return self._engaged


class AuditLogger:
    def __init__(self, filepath: Path = AUDIT_FILE) -> None:
        self._filepath = filepath
        self._lock = threading.Lock()
        self._records_by_id: dict[str, dict[str, Any]] = {}
        self._preload_recent()

    def _preload_recent(self) -> None:
        if not self._filepath.exists():
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        aid = record.get("action_id")
                        if aid:
                            self._records_by_id[aid] = record
        except Exception:
            pass

    def log_action(
        self,
        incident_id: str,
        action: str,
        params: dict[str, Any],
        dry_run: bool,
        status: str,
        detail: str,
        caller: str,
        previous_state: dict[str, Any] | None = None,
        action_id: str | None = None,
    ) -> str:
        aid = action_id or str(uuid.uuid4())
        record = {
            "action_id": aid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "incident_id": incident_id or "manual",
            "action": action,
            "params": params,
            "dry_run": dry_run,
            "status": status,
            "detail": detail,
            "caller": caller,
            "previous_state": previous_state,
        }

        with self._lock:
            self._records_by_id[aid] = record
            try:
                self._filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(self._filepath, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, separators=(",", ":")) + "\n")
            except Exception:
                pass

        return aid

    def get_audit_records(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self._filepath.exists():
            return []
        records: list[dict[str, Any]] = []
        with self._lock:
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in lines[-limit:]:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            except Exception:
                return []
        records.reverse()
        return records

    def get_action_by_id(self, action_id: str) -> dict[str, Any] | None:
        with self._lock:
            if action_id in self._records_by_id:
                return self._records_by_id[action_id]
        if not self._filepath.exists():
            return None
        with self._lock:
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    for line in reversed(f.readlines()):
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            if rec.get("action_id") == action_id:
                                self._records_by_id[action_id] = rec
                                return rec
            except Exception:
                pass
        return None


killswitch = KillSwitch()
audit_logger = AuditLogger()
