from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel

from app.config import DATA_DIR
from app.proposer import Proposal

logger = logging.getLogger("oncall-agent.approval")

ACTION_API_SECRET = os.environ.get("ACTION_API_SECRET", "change-me-locally")
ONCALL_APPROVAL_TTL_S = int(os.environ.get("ONCALL_APPROVAL_TTL_S", 900))


class IncidentState(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    DIAGNOSED = "DIAGNOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    ROLLED_BACK = "ROLLED_BACK"
    ESCALATED = "ESCALATED"


class IncidentRecord(BaseModel):
    incident_id: str
    state: IncidentState = IncidentState.DETECTED
    detected_at: str
    updated_at: str
    fingerprint: str = ""
    symptoms: list[dict[str, Any]] = []
    diagnosis: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    proposals: list[dict[str, Any]] = []
    approved_proposal_index: int | None = None
    approval_token: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    rejection_reason: str | None = None
    execution_results: list[dict[str, Any]] = []
    verification: dict[str, Any] | None = None
    escalation: dict[str, Any] | None = None
    report_path: str | None = None
    timeline: list[dict[str, Any]] = []

    def add_timeline(self, event: str, detail: str = "") -> None:
        self.timeline.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "detail": detail,
        })
        self.updated_at = datetime.now(timezone.utc).isoformat()


class ApprovalStore:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or (DATA_DIR / "incidents")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._incidents: dict[str, IncidentRecord] = {}
        self._lock = Lock()
        self._load_all()

    def _path(self, incident_id: str) -> Path:
        return self._dir / incident_id / "incident.json"

    def _load_all(self) -> None:
        for f in self._dir.glob("*/incident.json"):
            try:
                rec = IncidentRecord.model_validate_json(f.read_text())
                self._incidents[rec.incident_id] = rec
            except Exception:
                pass

    def _persist(self, rec: IncidentRecord) -> None:
        try:
            p = self._path(rec.incident_id)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(rec.model_dump_json(indent=2))
        except Exception as e:
            logger.error("Failed to persist incident %s: %s", rec.incident_id, e)

    def create(self, incident_id: str, fingerprint: str, symptoms: list[dict[str, Any]]) -> IncidentRecord:
        now = datetime.now(timezone.utc).isoformat()
        rec = IncidentRecord(
            incident_id=incident_id,
            detected_at=now,
            updated_at=now,
            fingerprint=fingerprint,
            symptoms=symptoms,
        )
        rec.add_timeline("DETECTED", f"Alert fired with {len(symptoms)} symptoms")
        with self._lock:
            self._incidents[incident_id] = rec
            self._persist(rec)
        return rec

    def get(self, incident_id: str) -> IncidentRecord | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def list_all(self) -> list[IncidentRecord]:
        with self._lock:
            return list(self._incidents.values())

    def update(self, rec: IncidentRecord) -> None:
        with self._lock:
            self._incidents[rec.incident_id] = rec
            self._persist(rec)

    def transition(self, rec: IncidentRecord, new_state: IncidentState, detail: str = "") -> None:
        rec.state = new_state
        rec.add_timeline(new_state.value, detail)
        self.update(rec)

    def mint_approval_token(
        self,
        incident_id: str,
        action: str,
        params: dict[str, Any],
        ttl_s: int = ONCALL_APPROVAL_TTL_S,
    ) -> str:
        exp = int(time.time()) + ttl_s
        payload = json.dumps(
            {"incident_id": incident_id, "action": action, "params": params, "exp": exp},
            sort_keys=True,
        )
        sig = hmac.new(
            ACTION_API_SECRET.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        token_data = json.dumps({"payload": payload, "sig": sig})
        import base64
        return base64.b64encode(token_data.encode()).decode()

    def verify_approval_token(
        self,
        token: str,
        incident_id: str,
        action: str,
        params: dict[str, Any],
    ) -> tuple[bool, str]:
        import base64
        try:
            decoded = base64.b64decode(token.encode()).decode()
            token_data = json.loads(decoded)
            payload_str = token_data["payload"]
            sig = token_data["sig"]
            expected_sig = hmac.new(
                ACTION_API_SECRET.encode(),
                payload_str.encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return False, "Token signature mismatch"
            payload = json.loads(payload_str)
            if payload.get("incident_id") != incident_id:
                return False, "Token incident_id mismatch"
            if payload.get("action") != action:
                return False, "Token action mismatch"
            if json.dumps(payload.get("params", {}), sort_keys=True) != json.dumps(params, sort_keys=True):
                return False, "Token params mismatch"
            if int(payload.get("exp", 0)) < int(time.time()):
                return False, "Token expired"
            return True, "ok"
        except Exception as e:
            return False, f"Token decode error: {e}"


approval_store = ApprovalStore()
