from __future__ import annotations

from typing import Any

from oncall.contracts import Alert
from oncall.events import EventLog
from oncall.ledger import EvidenceLedger


async def investigate(alert: Alert, ledger: EvidenceLedger, events: EventLog) -> dict[str, Any]:
    del ledger
    events.emit("agent_step", {"alert_id": alert.alert_id, "status": "uncertain_escalate"})
    return {
        "incident_id": alert.alert_id,
        "status": "uncertain_escalate",
        "root_cause_component": None,
        "root_cause": "Insufficient evidence",
        "fault_class": "unknown",
        "confidence": 0.0,
        "evidence_ids": [],
        "affected_services": [alert.service] if alert.service else [],
        "reasoning_steps": [],
    }
