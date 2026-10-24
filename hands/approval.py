# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
"""Human approval enforcement gate for Hands."""

from .kill_switch import KillSwitch
from .models import ApprovalDecision, ActionPlan, utc_now_iso
from .store import HandsStore


class ApprovalGate:
    def __init__(self, store: HandsStore, kill_switch: KillSwitch):
        self.store = store
        self.kill_switch = kill_switch

    def record_decision(
        self,
        incident_id: str,
        plan_digest: str,
        decision: str,
        operator: str,
        reason: str = "",
        expires_at: str | None = None,
    ) -> dict:
        plan = self.store.get_plan(plan_digest)
        if not plan:
            raise ValueError(f"Cannot approve/reject unknown plan digest: {plan_digest}")

        if plan["incident_id"] != incident_id:
            raise ValueError(f"Plan digest {plan_digest} belongs to incident {plan['incident_id']}, not {incident_id}")

        decision_obj = ApprovalDecision(
            incident_id=incident_id,
            plan_digest=plan_digest,
            decision=decision,
            operator=operator,
            reason=reason,
            expires_at=expires_at,
        )

        data = decision_obj.to_dict()
        self.store.save_approval(data)
        return data

    def verify_authorization(self, plan: ActionPlan, current_iso: str | None = None) -> tuple[bool, str]:
        # 1. Kill switch check
        if self.kill_switch.is_engaged():
            return False, "Kill switch is active. Mutations are forbidden."

        # 2. Check if already dispatched (single dispatch / idempotency)
        if self.store.is_dispatched(plan.digest):
            return False, f"Plan with digest {plan.digest} has already been dispatched. Re-dispatch is prohibited."

        # 3. Lookup approval record
        approval_dict = self.store.get_approval(plan.digest)
        if not approval_dict:
            return False, f"No human approval decision recorded for plan digest {plan.digest}."

        decision = ApprovalDecision(
            incident_id=approval_dict["incident_id"],
            plan_digest=approval_dict["plan_digest"],
            decision=approval_dict["decision"],
            operator=approval_dict["operator"],
            reason=approval_dict.get("reason", ""),
            approved_at=approval_dict.get("approved_at"),
            expires_at=approval_dict.get("expires_at"),
        )

        # 4. Check decision
        if decision.decision != "approved":
            return False, f"Plan was explicitly rejected by operator '{decision.operator}': {decision.reason}"

        # 5. Check digest binding
        if not decision.is_valid(plan.digest, current_iso=current_iso):
            now_iso = current_iso or utc_now_iso()
            if decision.expires_at and now_iso > decision.expires_at:
                return False, f"Approval expired at {decision.expires_at} (current time {now_iso}). Fresh review required."
            return False, "Approval record does not match current plan digest."

        return True, f"Authorized by '{decision.operator}' at {decision.approved_at}."
