"""Human approval gate for remediation actions."""
from __future__ import annotations

from enum import Enum
from typing import Callable, Optional
from ..models.action import RemediationAction, ApprovalStatus


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalGate:
    """Manages human approval before executing remediation actions."""

    def __init__(
        self,
        require_approval: bool = True,
        approval_callback: Optional[Callable[[RemediationAction], bool]] = None,
    ) -> None:
        self.require_approval = require_approval
        self.approval_callback = approval_callback

    def request_approval(self, action: RemediationAction) -> ApprovalDecision:
        """Prompt or evaluate approval for the requested action."""
        if not self.require_approval or not action.requires_approval:
            action.approval_status = ApprovalStatus.BYPASSED
            return ApprovalDecision.APPROVED

        if self.approval_callback:
            approved = self.approval_callback(action)
            action.approval_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            return ApprovalDecision.APPROVED if approved else ApprovalDecision.REJECTED

        # Default fallback: reject unless explicitly configured
        action.approval_status = ApprovalStatus.PENDING
        return ApprovalDecision.REJECTED
