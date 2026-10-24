# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
"""Durable, crash-resilient kill switch for Hands."""

from .models import utc_now_iso
from .store import HandsStore


class KillSwitchEngagedError(RuntimeError):
    """Raised when an action is attempted while the kill switch is active."""


class KillSwitch:
    def __init__(self, store: HandsStore):
        self.store = store

    def is_engaged(self) -> bool:
        record = self.store.get_kill_switch()
        return record.get("engaged", False)

    def status(self) -> dict:
        return self.store.get_kill_switch()

    def engage(self, operator: str, reason: str) -> dict:
        if not operator or not isinstance(operator, str):
            raise ValueError("Operator identifier is required")
        if not reason or not isinstance(reason, str):
            raise ValueError("Reason is required to engage kill switch")

        now = utc_now_iso()
        self.store.set_kill_switch(engaged=True, updated_at=now, operator=operator, reason=reason)
        return {
            "engaged": True,
            "updated_at": now,
            "operator": operator,
            "reason": reason,
        }

    def reset(self, operator: str, reason: str) -> dict:
        if not operator or not isinstance(operator, str):
            raise ValueError("Operator identifier is required")
        if not reason or not isinstance(reason, str):
            raise ValueError("Reason is required to reset kill switch")

        now = utc_now_iso()
        self.store.set_kill_switch(engaged=False, updated_at=now, operator=operator, reason=reason)
        return {
            "engaged": False,
            "updated_at": now,
            "operator": operator,
            "reason": reason,
        }

    def check_clear(self) -> None:
        rec = self.store.get_kill_switch()
        if rec.get("engaged", False):
            raise KillSwitchEngagedError(
                f"Kill switch is active (engaged by '{rec.get('operator')}' at {rec.get('updated_at')}: {rec.get('reason')}). All dispatches are halted."
            )
