"""Data models for remediation actions and approval."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    REVERT_FAULT_FLAG = "REVERT_FAULT_FLAG"
    RESTART_SERVICE = "RESTART_SERVICE"
    SCALE_SERVICE = "SCALE_SERVICE"
    RATE_LIMIT = "RATE_LIMIT"
    CUSTOM = "CUSTOM"


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
    requires_approval: bool = True
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    dry_run: bool = True
    executed_at: Optional[str] = None
    execution_result: Optional[str] = None
    recovery_verified: bool = False
