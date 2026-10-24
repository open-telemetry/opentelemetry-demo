"""Action backends. Every backend accepts only an ApprovedAction issued by ApprovalGate."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..agent.transcript import utc_now
from ..approval.gate import ACTION_ROLE, ROLLBACK_ROLE, ApprovalError, ApprovedAction
from ..config import Settings
from ..models.action import RemediationAction, is_allowlisted

BLOCKED_CONTRACT = "BLOCKED: Action API contract not received"

AuditFn = Callable[[Dict[str, Any]], None]


class ActionAPINotConfiguredError(RuntimeError):
    """The organisers' Action API contract (endpoint, catalog, auth, payloads) is not available."""


class ActionRefusedError(PermissionError):
    """A backend refused a request: no valid approval, or an action type off the allowlist."""


def log_audit_event(audit_log_path: Path | str, event: Dict[str, Any]) -> None:
    """Append a structured audit event to the audit log."""
    path = Path(audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


@dataclass
class ActionResult:
    status: str
    action_id: str
    action_type: str
    target_service: str
    role: str
    dry_run: bool
    backend: str
    message: str
    request: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ActionBackend(ABC):
    name = "abstract"
    dry_run = True

    def __init__(self, audit: Optional[AuditFn] = None) -> None:
        self.audit = audit
        self.refusals: List[Dict[str, Any]] = []

    def execute(self, approved: ApprovedAction, expected_action_id: Optional[str] = None) -> ActionResult:
        return self._perform(self._admit(approved, ACTION_ROLE, expected_action_id), ACTION_ROLE)

    def rollback(self, approved: ApprovedAction, expected_action_id: Optional[str] = None) -> ActionResult:
        return self._perform(self._admit(approved, ROLLBACK_ROLE, expected_action_id), ROLLBACK_ROLE)

    def _admit(self, approved: Any, role: str, expected_action_id: Optional[str]) -> RemediationAction:
        if not isinstance(approved, ApprovedAction):
            self._refuse(role, approved, f"requires an ApprovedAction issued by ApprovalGate, "
                                         f"got {type(approved).__name__}")
        try:
            action = approved.redeem(role, expected_action_id)
        except ApprovalError as e:
            self._refuse(role, approved, str(e))
        if not is_allowlisted(action.action_type):
            self._refuse(role, action, f"action type {action.action_type.value} is not on the allowlist")
        return action

    def _refuse(self, role: str, obj: Any, reason: str) -> None:
        try:
            action_id = getattr(obj, "action_id", None)
        except AttributeError:
            action_id = None
        event = {"timestamp": utc_now(), "event": "BACKEND_REFUSED", "backend": self.name,
                 "operation": role, "action_id": action_id, "reason": reason}
        self.refusals.append(event)
        if self.audit:
            self.audit(event)
        raise ActionRefusedError(reason)

    @abstractmethod
    def _perform(self, action: RemediationAction, role: str) -> ActionResult:
        ...


class DryRunBackend(ActionBackend):
    """Records the request it would send and makes no network call."""

    name = "dry_run"
    dry_run = True

    def __init__(self, audit: Optional[AuditFn] = None) -> None:
        super().__init__(audit)
        self.requests: List[Dict[str, Any]] = []

    def _perform(self, action: RemediationAction, role: str) -> ActionResult:
        request = {"operation": role, "action_id": action.action_id, "action_type": action.action_type.value,
                   "target_service": action.target_service, "parameters": action.parameters,
                   "format": "internal request; the Action API payload format is not published yet"}
        self.requests.append(request)
        return ActionResult(
            status="DRY_RUN", action_id=action.action_id, action_type=action.action_type.value,
            target_service=action.target_service, role=role, dry_run=True, backend=self.name,
            message=f"DRY RUN: {action.action_type.value} on '{action.target_service}' was recorded, "
                    f"not sent. No Action API call was made.",
            request=request)


class HttpActionBackend(ActionBackend):
    """The organisers' Action API. Stays BLOCKED until its contract is published."""

    name = "action_api"
    dry_run = False

    def __init__(self, settings: Settings, audit: Optional[AuditFn] = None) -> None:
        super().__init__(audit)
        if not (settings.action_api_endpoint and settings.action_api_catalog_path):
            raise ActionAPINotConfiguredError(
                f"{BLOCKED_CONTRACT} (ACTION_API_ENDPOINT and ACTION_API_CATALOG are not set)")
        self.endpoint = settings.action_api_endpoint
        self.catalog_path = settings.action_api_catalog_path

    def _perform(self, action: RemediationAction, role: str) -> ActionResult:
        raise ActionAPINotConfiguredError(f"{BLOCKED_CONTRACT} (paths, auth and payloads are not defined)")


def get_backend(settings: Settings, dry_run: bool = True, audit: Optional[AuditFn] = None) -> ActionBackend:
    """Dry run unless both --no-dry-run and DRY_RUN_MODE=false; a live request without a
    configured Action API raises ActionAPINotConfiguredError instead of silently dry-running."""
    if dry_run or settings.dry_run_mode:
        return DryRunBackend(audit=audit)
    return HttpActionBackend(settings, audit=audit)
