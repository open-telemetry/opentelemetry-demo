#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
AI On-Call Engineer: End-to-End CLI Pipeline (Checkpoints 1, 2, 3, and 4).
Supports:
- Live/Offline Telemetry Investigation (The Eyes)
- Downstream Root-Cause Isolation (The Brain)
- Human Approval Barrier & Token Gate (The Safety Barrier)
- Action API Allowlisted Execution with Dry-Run & Kill-Switch (The Hands)
- Automated Recovery Polling & Rollback on Failure
- Adversarial Reviewer Audit (Stretch Goal 2)
- Incident Memory Precedent Matching (Stretch Goal 1)
- Prevention & Post-Mortem Reporting (The Voice)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime, timezone
from oncall.models import IncidentAlert
from oncall.agent import AIOnCallAgent
from oncall.safety.approval_gate import HumanApprovalGate
from oncall.safety.reviewer_agent import ReviewerAgent
from oncall.safety.recovery_verifier import RecoveryVerifier
from oncall.actions.action_manager import ActionManager
from oncall.memory.incident_memory import IncidentMemory
from oncall.reporter import IncidentReporter


def main():
    parser = argparse.ArgumentParser(description="AI On-Call Engineer Production CLI")
    parser.add_argument("--service", default="cart", help="Target service to investigate (default: cart)")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve actions in automated evaluation benchmarks")
    parser.add_argument("--dry-run", action="store_true", help="Validate action without mutating system state (Slide 2 Step 5)")
    parser.add_argument("--kill-switch", action="store_true", help="Emergency kill switch: abort execution and escalate immediately")
    args = parser.parse_args()

    print("=" * 80)
    print("  BOSCH 'INCIDENT ZERO' HACKATHON: AI ON-CALL ENGINEER (COMPLETE PIPELINE)")
    print("=" * 80)

    # Emergency Kill Switch Check
    if args.kill_switch:
        print("\n[EMERGENCY KILL SWITCH ACTIVATED]")
        print("  All automated remediation actions are immediately halted.")
        print("  Escalating incident directly to Senior Human On-Call Engineer.")
        print("=" * 80)
        sys.exit(0)

    # 1. Incident Alert Ingress
    alert = IncidentAlert(
        alert_id=f"INC-{args.service.upper()}-001",
        service_name=args.service,
        title=f"{args.service.capitalize()}DegradedPerformance",
        severity="critical" if args.service in ("cart", "checkout") else ("warning" if args.service == "ad" else "info"),
        started_at=datetime.now(timezone.utc),
        summary=f"P95 response latency exceeded SLA threshold on service '{args.service}'."
    )
    print(f"\n[ALERT RECEIVED] {alert.title} on '{alert.service_name}' ({alert.severity.upper()})")

    # Stretch Goal 1: Incident Memory Precedent Lookup
    memory = IncidentMemory()
    match = memory.lookup(args.service, alert.title)
    if match:
        print(f"\n[*] Incident Memory Match ({match['similarity_score']*100:.0f}% similarity to past incident):")
        print(f"    Prior Resolution: {match['prior_resolution']}")
        print(f"    Suggested Action: {match['proven_action']}")

    # 2. CHECKPOINT 1 & 2: Investigation & Evidence-Based Diagnosis (The Eyes & Brain)
    print("\n[PHASE 1: INVESTIGATION & EVIDENCE-BASED DIAGNOSIS]")
    agent = AIOnCallAgent()
    diagnosis = agent.investigate(alert)

    print(f">> Target Service      : {diagnosis.target_service}")
    print(f">> Root Cause Service  : {diagnosis.root_cause_service} {'(Downstream Culprit!)' if diagnosis.root_cause_service != diagnosis.target_service else ''}")
    print(f">> Failure Mode        : {diagnosis.failure_mode}")
    print(f">> Calibrated Conf.    : {diagnosis.confidence_score * 100:.1f}%")
    print(f">> Citations Gathered  : {len(diagnosis.citations)} telemetry sources")

    if diagnosis.failure_mode == "NORMAL_BASELINE_HEALTH":
        print("\n[VERDICT] Service is healthy. Alert flagged as False Positive. No remediation required.")
        return

    # Stretch Goal 2: Adversarial Reviewer Agent Audit
    print("\n[PHASE 2: ADVERSARIAL REVIEWER AGENT AUDIT]")
    reviewer = ReviewerAgent()
    review_verdict = reviewer.review_diagnosis(diagnosis)
    print(f">> Reviewer Verdict    : {review_verdict['verdict']}")
    print(f">> Audit Summary       : {review_verdict['summary']}")
    for cp in review_verdict["checks_passed"]:
        print(f"   + {cp}")

    if not review_verdict["approved"]:
        print("\n[BLOCKED BY REVIEWER] Diagnosis challenged. Halting for investigation.")
        return

    # 3. CHECKPOINT 3: Human Approval Barrier & Token Gate (The Safety Gate)
    print("\n[PHASE 3: HUMAN-IN-THE-LOOP APPROVAL GATE]")
    if args.dry_run:
        print(">> Mode: DRY-RUN ENABLED (No actual mutations will be performed)")

    approval_gate = HumanApprovalGate(auto_approve_in_dev=args.auto_approve)
    proposed_action = {
        "action": diagnosis.action_type,
        "target": diagnosis.root_cause_service,
        "detail": diagnosis.recommended_action
    }
    decision = approval_gate.request_approval(diagnosis, proposed_action)

    if not decision.approved:
        print("\n[ABORTED] Remediation rejected or escalated. Incident remains open.")
        return

    print(f">> Approval Granted (Token: {decision.token}) by {decision.approver}")

    # 4. CHECKPOINT 3: Action Execution (The Hands)
    print("\n[PHASE 4: ACTION API EXECUTION]")
    action_mgr = ActionManager()
    execution_result = action_mgr.execute_action(
        action_type=diagnosis.action_type,
        target_service=diagnosis.root_cause_service,
        auth_token=decision.token,
        dry_run=args.dry_run
    )
    print(f">> Action Outcome: {execution_result.get('message') or execution_result.get('error')}")

    # 5. CHECKPOINT 3: Post-Action Recovery Verification & Rollback
    print("\n[PHASE 5: RECOVERY TELEMETRY VERIFICATION]")
    verifier = RecoveryVerifier()
    verification_result = verifier.verify_recovery(service_name=args.service, timeout_seconds=10)

    if not verification_result.get("recovered") and not args.dry_run:
        print("\n[RECOVERY FAILED] System did not stabilize within verification window!")
        print(">> Triggering automated safety rollback...")
        rollback_res = action_mgr.rollback_last_action()
        print(f">> {rollback_res.get('message')}")
    else:
        # Save to incident memory on successful mitigation
        memory.store_resolved_incident(
            incident_id=alert.alert_id,
            service=args.service,
            root_cause_service=diagnosis.root_cause_service,
            failure_mode=diagnosis.failure_mode,
            proven_action=diagnosis.action_type,
            summary=diagnosis.explanation
        )

    # 6. CHECKPOINT 4: Post-Mortem Incident Report & Prevention (The Voice)
    print("\n[PHASE 6: POST-MORTEM INCIDENT REPORT & PREVENTION]")
    report_md = IncidentReporter.generate_markdown_report(
        alert=alert,
        diagnosis=diagnosis,
        approval=decision.to_dict(),
        execution=execution_result,
        verification=verification_result,
        reviewer_audit=review_verdict
    )
    print(report_md)


if __name__ == "__main__":
    main()
