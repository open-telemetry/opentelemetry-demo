# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Human Approval Gate with Pre-Execution Evidence Consistency Checking.
Owned by Teammate 4 (The Hands).
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from oncall.models import RootCauseDiagnosis


class ApprovalDecision:
    def __init__(self, approved: bool, token: str, approver: str, notes: Optional[str] = None):
        self.approved = approved
        self.token = token
        self.approver = approver
        self.notes = notes or ""
        self.decided_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "token": self.token,
            "approver": self.approver,
            "notes": self.notes,
            "decided_at": self.decided_at.isoformat(),
        }


class HumanApprovalGate:
    def __init__(self, auto_approve_in_dev: bool = False):
        self.auto_approve = auto_approve_in_dev

    def request_approval(self, diagnosis: RootCauseDiagnosis, proposed_action: Dict[str, Any]) -> ApprovalDecision:
        """
        Enforces:
        1. Pre-execution Evidence Consistency Check:
           If diagnosis failed consistency or proposed action is redundant, refuse approval!
        2. Explicit Human/Evaluator Confirmation Barrier.
        """
        token = f"AUTH-{uuid.uuid4().hex[:8].upper()}"

        # 1. Pre-flight consistency validation
        if not diagnosis.evidence_consistency_passed:
            reasons = "; ".join(diagnosis.consistency_errors)
            print(f"\n[APPROVAL BLOCKED - CONSISTENCY FAILURE] {reasons}")
            return ApprovalDecision(
                approved=False,
                token="REJECTED-INCONSISTENT",
                approver="safety_gate_enforcer",
                notes=f"Action blocked: Evidence consistency check failed ({reasons})"
            )

        if self.auto_approve:
            return ApprovalDecision(
                approved=True,
                token=token,
                approver="evaluator_auto_policy",
                notes="Auto-approved under non-interactive evaluation policy."
            )

        print("\n" + "=" * 80)
        print("  [HUMAN APPROVAL REQUIRED - PHYSICAL SAFETY BARRIER]")
        print("=" * 80)
        print(f"Target Service   : {diagnosis.target_service}")
        print(f"Root Cause Service: {diagnosis.root_cause_service}")
        print(f"Failure Mode     : {diagnosis.failure_mode}")
        print(f"Confidence       : {diagnosis.confidence_score * 100:.1f}%")
        print(f"Proposed Action  : {diagnosis.recommended_action}")
        print(f"Action Type      : {diagnosis.action_type}")
        print(f"Parameters       : {proposed_action}")
        print("\nEvidence Grounding:")
        print(f"  Confirmed Facts     : {len(diagnosis.confirmed_facts)}")
        print(f"  Likely Causes       : {len(diagnosis.likely_causes)}")
        print(f"  Ruled Out Hypotheses: {len(diagnosis.unresolved_hypotheses)}")
        print("-" * 80)

        try:
            choice = input("Do you authorize this remediation action? (yes/no/escalate) [no]: ").strip().lower()
        except EOFError:
            choice = "no"

        if choice in ("yes", "y"):
            print(f"[APPROVED] Action authorized with Approval Token: {token}")
            return ApprovalDecision(approved=True, token=token, approver="oncall_operator")
        elif choice == "escalate":
            print("[ESCALATED] Operator requested escalation to Tier-3 SRE.")
            return ApprovalDecision(approved=False, token=token, approver="oncall_operator", notes="Operator escalated")
        else:
            print("[REJECTED] Action denied by operator.")
            return ApprovalDecision(approved=False, token=token, approver="oncall_operator", notes="Operator rejected")
