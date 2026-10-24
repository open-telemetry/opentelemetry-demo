# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
"""Main coordinator for Hands: gatekeeping, dispatch, audit, verification, and rollback."""

import uuid

from .adapter import ActionApiAdapter
from .approval import ApprovalGate
from .kill_switch import KillSwitch, KillSwitchEngagedError
from .models import ActionPlan, ActionAttempt, VerificationResult, utc_now_iso
from .store import HandsStore
from .verifier import RecoveryVerifier


class HandsExecutor:
    def __init__(
        self,
        store: HandsStore,
        approval_gate: ApprovalGate,
        kill_switch: KillSwitch,
        adapter: ActionApiAdapter,
        verifier: RecoveryVerifier,
    ):
        self.store = store
        self.approval_gate = approval_gate
        self.kill_switch = kill_switch
        self.adapter = adapter
        self.verifier = verifier

    def dispatch(self, plan: ActionPlan, dry_run: bool = False) -> dict:
        now_iso = utc_now_iso()

        # 1. Verification of Human Authorization
        authorized, reason = self.approval_gate.verify_authorization(plan, current_iso=now_iso)
        if not authorized:
            return {
                "success": False,
                "status": "unauthorized",
                "message": reason,
                "incident_id": plan.incident_id,
                "plan_digest": plan.digest,
            }

        # 2. Check kill switch immediately before dispatch
        if self.kill_switch.is_engaged():
            return {
                "success": False,
                "status": "halted_by_kill_switch",
                "message": "Kill switch is engaged. Execution halted.",
                "incident_id": plan.incident_id,
                "plan_digest": plan.digest,
            }

        # 3. Handle Dry Run
        if dry_run:
            return {
                "success": True,
                "status": "dry_run",
                "message": "Dry run validated successfully. No mutations performed.",
                "incident_id": plan.incident_id,
                "plan_digest": plan.digest,
                "planned_action": plan.to_dict(),
            }

        # 4. Generate Idempotency Key & Record in Ledger
        attempt_id = f"att-{uuid.uuid4().hex[:12]}"
        self.store.record_dispatch(
            incident_id=plan.incident_id,
            plan_digest=plan.digest,
            attempt_id=attempt_id,
            dispatched_at=now_iso,
            status="dispatched",
        )

        # 5. Execute Action through Adapter
        exec_res = self.adapter.execute(
            action_type=plan.action_type,
            target=plan.target,
            parameters=plan.parameters,
            idempotency_key=attempt_id,
        )

        # 6. Save Audit Record
        audit_record = {
            "attempt_id": attempt_id,
            "incident_id": plan.incident_id,
            "plan_digest": plan.digest,
            "action_type": plan.action_type,
            "target": plan.target,
            "parameters": plan.parameters,
            "dispatched_at": exec_res["dispatched_at"],
            "status": exec_res["status"],
            "duration_ms": exec_res["duration_ms"],
            "response_data": exec_res["response_data"],
            "error_message": exec_res["error_message"],
        }
        self.store.save_audit(audit_record)

        if exec_res["status"] != "ok":
            return {
                "success": False,
                "status": "action_failed",
                "message": f"Action execution failed: {exec_res.get('error_message')}",
                "incident_id": plan.incident_id,
                "plan_digest": plan.digest,
                "attempt": audit_record,
            }

        # 7. Verification of Recovery
        criteria = plan.data.get("verification_criteria", {})
        verif_res = self.verifier.verify(
            incident_id=plan.incident_id,
            plan_digest=plan.digest,
            action_time_iso=exec_res["dispatched_at"],
            criteria=criteria,
            target_service=plan.target,
        )
        self.store.save_verification(verif_res.to_dict())

        # 8. Handle Rollback if Not Recovered
        rollback_executed = False
        rollback_result = None

        if verif_res.verdict == VerificationResult.NOT_RECOVERED:
            rollback_plan_data = plan.data.get("rollback_action")
            if rollback_plan_data and not self.kill_switch.is_engaged():
                rb_attempt_id = f"rb-{uuid.uuid4().hex[:12]}"
                rollback_result = self.adapter.execute(
                    action_type=rollback_plan_data.get("action_type", ""),
                    target=rollback_plan_data.get("target", plan.target),
                    parameters=rollback_plan_data.get("parameters", {}),
                    idempotency_key=rb_attempt_id,
                )
                rollback_executed = True
                self.store.save_audit({
                    "attempt_id": rb_attempt_id,
                    "incident_id": plan.incident_id,
                    "plan_digest": plan.digest + "-rollback",
                    "action_type": rollback_plan_data.get("action_type", ""),
                    "target": rollback_plan_data.get("target", plan.target),
                    "parameters": rollback_plan_data.get("parameters", {}),
                    "dispatched_at": rollback_result["dispatched_at"],
                    "status": rollback_result["status"],
                    "duration_ms": rollback_result["duration_ms"],
                    "response_data": rollback_result["response_data"],
                    "error_message": rollback_result["error_message"],
                })

        return {
            "success": verif_res.verdict == VerificationResult.RECOVERED,
            "status": "completed",
            "incident_id": plan.incident_id,
            "plan_digest": plan.digest,
            "action_attempt": audit_record,
            "verification": verif_res.to_dict(),
            "rollback_executed": rollback_executed,
            "rollback_result": rollback_result,
        }
