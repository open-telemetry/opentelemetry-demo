"""Data models for remediation actions and approval."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    RESTART_SERVICE = "RESTART_SERVICE"
    THROTTLE_LOAD_GENERATOR = "THROTTLE_LOAD_GENERATOR"
    RESTORE_LOAD_GENERATOR = "RESTORE_LOAD_GENERATOR"
    SCALE_SERVICE = "SCALE_SERVICE"
    SET_FEATURE_FLAG = "SET_FEATURE_FLAG"
    REVERT_FAULT_FLAG = "REVERT_FAULT_FLAG"
    RATE_LIMIT = "RATE_LIMIT"
    CUSTOM = "CUSTOM"


# Placeholder catalog until the organisers' Action API catalog arrives: each allowlisted action
# mapped to the action type that rolls it back (None = no rollback).
ACTION_CATALOG: Dict[ActionType, Optional[ActionType]] = {
    ActionType.RESTART_SERVICE: None,
    ActionType.THROTTLE_LOAD_GENERATOR: ActionType.RESTORE_LOAD_GENERATOR,
    ActionType.RESTORE_LOAD_GENERATOR: ActionType.THROTTLE_LOAD_GENERATOR,
    ActionType.SCALE_SERVICE: ActionType.SCALE_SERVICE,
    ActionType.SET_FEATURE_FLAG: None,
}
ALLOWED_ACTION_TYPES = frozenset(ACTION_CATALOG)
# Executed without a rollback, only after the human acknowledges that it cannot be undone.
IRREVERSIBLE_ACTIONS = frozenset({ActionType.RESTART_SERVICE})


def is_allowlisted(action_type: Any) -> bool:
    try:
        return ActionType(getattr(action_type, "value", action_type)) in ALLOWED_ACTION_TYPES
    except ValueError:
        return False


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BYPASSED = "BYPASSED"


class RemediationAction(BaseModel):
    """Represents a planned or executed remediation action."""
    action_id: str
    action_type: ActionType
    target_service: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    rollback: Optional["RemediationAction"] = None
    irreversible: bool = False
    requires_approval: bool = True
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approver: Optional[str] = None
    approved_at: Optional[str] = None
    approval_channel: Optional[str] = None
    dry_run: bool = True
    backend: Optional[str] = None
    executed_at: Optional[str] = None
    execution_result: Optional[str] = None
    recovery_verified: bool = False


RemediationAction.model_rebuild()
