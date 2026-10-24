#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
AI On-Call Engineer: End-to-End CLI Pipeline (Checkpoints 1 & 2).
Run: python oncall/cli.py [--auto-approve]
"""

import argparse
import os
import sys

# Ensure repository root is in search path and UTF-8 encoding
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime, timezone
from oncall.models import IncidentAlert
from oncall.agent import AIOnCallAgent
from oncall.safety.approval_gate import HumanApprovalGate
from oncall.actions.flagd_action import FlagdActionClient
from oncall.safety.recovery_verifier import RecoveryVerifier
from oncall.reporter import IncidentReporter


def main():
    parser = argparse.ArgumentParser(description="AI On-Call Engineer CLI")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve actions (useful for evaluation benchmarks)")
    parser.add_argument("--service", default="cart", help="Target service to investigate (default: cart)")
    args = parser.parse_args()

    print("=" * 80)
    print("  BOSCH 'INCIDENT ZERO' HACKATHON: AI ON-CALL ENGINEER (CHECKPOINTS 1 & 2)")
    print("=" * 80)

    # 1. Trigger Incident Alert
    alert = IncidentAlert(
        alert_id="INC-2026-LIVE-001",
        service_name=args.service,
        title=f"{args.service.capitalize()}DegradedPerformance",
        severity="critical",
        started_at=datetime.now(timezone.utc),
        summary=f"P95 response latency exceeded 2000ms threshold on service '{args.service}'."
    )
    print(f"\n[ALERT RECEIVED] {alert.title} on '{alert.service_name}' ({alert.severity.upper()})")

    # 2. CHECKPOINT 1: Investigation & Diagnosis (The Brain + Eyes)
    agent = AIOnCallAgent()
    print("\n[PHASE 1: INVESTIGATION & EVIDENCE-BASED DIAGNOSIS]")
    diagnosis = agent.investigate(alert)

    print(f">> Diagnosis Complete: {diagnosis.failure_mode}")
    print(f">> Confidence Score  : {diagnosis.confidence_score * 100:.1f}%")
    print(f">> Citations Gathered: {len(diagnosis.citations)} telemetry sources")

    # 3. CHECKPOINT 2: Human Approval Barrier (Safety Gate)
    print("\n[PHASE 2: HUMAN-IN-THE-LOOP APPROVAL GATE]")
    approval_gate = HumanApprovalGate(auto_approve_in_dev=args.auto_approve)
    proposed_action = {
        "action": diagnosis.action_type,
        "target": diagnosis.target_service,
        "detail": diagnosis.recommended_action
    }
    decision = approval_gate.request_approval(diagnosis, proposed_action)

    if not decision.approved:
        print("\n[ABORTED] Remediation rejected or escalated. Incident remains open.")
        return

    # 4. CHECKPOINT 2: Action Execution (The Hands)
    print("\n[PHASE 3: ACTION API EXECUTION]")
    flagd_client = FlagdActionClient()
    execution_result = flagd_client.reset_flag(flag_name="cartFailure", target_variant="off", dry_run=False)
    print(f">> Action Result: {execution_result.get('message')}")

    # 5. CHECKPOINT 2: Post-Action Recovery Verification
    print("\n[PHASE 4: RECOVERY TELEMETRY VERIFICATION]")
    verifier = RecoveryVerifier()
    verification_result = verifier.verify_recovery(service_name=args.service, timeout_seconds=10)

    # 6. CHECKPOINT 2: Final Post-Mortem Report Generation
    print("\n[PHASE 5: POST-MORTEM INCIDENT REPORT]")
    report_md = IncidentReporter.generate_markdown_report(
        alert=alert,
        diagnosis=diagnosis,
        approval=decision.to_dict(),
        execution=execution_result,
        verification=verification_result,
    )
    print(report_md)


if __name__ == "__main__":
    main()
