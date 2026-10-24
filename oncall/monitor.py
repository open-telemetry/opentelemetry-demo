#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Autonomous AI On-Call Monitor & Notification Daemon.
Continuously monitors live microservices via Prometheus Golden Signals.
When an anomaly (latency spike / error rate) is detected:
1. Plays audio-visual alert notification (\a + colored banner).
2. Autonomously launches ReAct investigation (Jaeger, OpenSearch, Git).
3. Executes Adversarial Reviewer audit.
4. Pauses and prompts human on-call engineer for approval (yes/no/escalate).
5. Executes approved Action API fix.
6. Verifies recovery via live telemetry polling.
7. Emits structured post-mortem report and resumes monitoring.

Includes 60s incident cooldown to prevent alert spamming.
Run: python oncall/monitor.py [--interval 5] [--auto-approve]
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from oncall.models import IncidentAlert
from oncall.agent import AIOnCallAgent
from oncall.safety.approval_gate import HumanApprovalGate
from oncall.safety.reviewer_agent import ReviewerAgent
from oncall.safety.recovery_verifier import RecoveryVerifier
from oncall.actions.action_manager import ActionManager
from oncall.memory.incident_memory import IncidentMemory
from oncall.reporter import IncidentReporter
from oncall.tools.prometheus import PrometheusTool

MONITORED_SERVICES = [
    "cart", "checkout", "payment", "ad", "recommendation",
    "frontend", "product-catalog", "shipping", "email"
]

LATENCY_THRESHOLD_SEC = 1.0  # SLA threshold: 1000ms


class OnCallMonitor:
    def __init__(self, check_interval_sec: int = 5, auto_approve: bool = False, dry_run: bool = False, threshold_sec: float = 1.0):
        self.interval = check_interval_sec
        self.auto_approve = auto_approve
        self.dry_run = dry_run
        self.threshold_sec = threshold_sec
        self.prom_tool = PrometheusTool()
        self.agent = AIOnCallAgent(prom_tool=self.prom_tool)
        self.reviewer = ReviewerAgent()
        self.action_mgr = ActionManager()
        self.memory = IncidentMemory()
        self.verifier = RecoveryVerifier()
        self.approval_gate = HumanApprovalGate(auto_approve_in_dev=auto_approve)
        self.last_alert_time: Dict[str, float] = {}
        self.cooldown_sec = 60.0  # 60s cooldown per service to avoid spamming

    def play_alert_sound(self):
        """Emits terminal audible bell to alert the on-call engineer."""
        sys.stdout.write("\a\a")
        sys.stdout.flush()

    def check_service_health(self, service: str) -> Optional[IncidentAlert]:
        """Queries Prometheus for service Golden Signals and detects SLA violations."""
        now = time.time()
        last_time = self.last_alert_time.get(service, 0.0)
        if (now - last_time) < self.cooldown_sec:
            return None  # Under cooldown

        obs = self.prom_tool.inspect_service_metrics(service)
        p95 = obs.data.get("p95_latency_sec", 0.0)
        err_rate = obs.data.get("error_rate_rps", 0.0)

        # Trigger condition: P95 > threshold or error rate > 5 req/s
        if p95 >= self.threshold_sec or err_rate > 5.0:
            self.last_alert_time[service] = now
            alert_id = f"ALERT-{service.upper()}-{int(now)}"
            return IncidentAlert(
                alert_id=alert_id,
                service_name=service,
                title=f"{service.capitalize()}DegradedPerformance",
                severity="critical" if p95 > 2.0 or err_rate > 10.0 else "warning",
                started_at=datetime.now(timezone.utc),
                summary=(
                    f"Golden Signals Violation: P95 Latency = {p95*1000:.0f}ms (threshold: {self.threshold_sec*1000:.0f}ms), "
                    f"Error Rate = {err_rate:.1f} req/s."
                )
            )
        return None

    def handle_incident(self, alert: IncidentAlert):
        """Executes full triage, notification, approval, and remediation workflow."""
        self.play_alert_sound()
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

        print("\n" + "=" * 80)
        print(f"🚨 [INCIDENT DETECTED AT {now_str}]")
        print(f"   Service : {alert.service_name.upper()}")
        print(f"   Summary : {alert.summary}")
        print("=" * 80)

        # 1. Incident Memory Lookup
        mem_match = self.memory.lookup(alert.service_name, alert.title)
        if mem_match:
            print(f"[*] Incident Memory Precedent ({mem_match['similarity_score']*100:.0f}% match):")
            print(f"    Suggested Action: {mem_match['proven_action']}")
            print(f"    Prior Resolution: {mem_match['prior_resolution']}")

        # 2. ReAct Autonomous Investigation
        print("\n[PHASE 1: AUTONOMOUS TELEMETRY INVESTIGATION]")
        diagnosis = self.agent.investigate(alert)

        print(f">> Target Service      : {diagnosis.target_service}")
        print(f">> Root Cause Service  : {diagnosis.root_cause_service} {'(Downstream Culprit!)' if diagnosis.root_cause_service != diagnosis.target_service else ''}")
        print(f">> Failure Mode        : {diagnosis.failure_mode}")
        print(f">> Calibrated Conf.    : {diagnosis.confidence_score * 100:.1f}%")
        print(f">> Citations Gathered  : {len(diagnosis.citations)} telemetry sources")

        if diagnosis.failure_mode == "NORMAL_BASELINE_HEALTH" or diagnosis.action_type == "NO_ACTION" or diagnosis.telemetry_reconciliation_status in ("NOMINAL_BASELINE", "RECOVERED_SINCE_TRIGGER"):
            print("\n[RESOLVED / NO ACTION REQUIRED] Telemetry confirms service is nominal or auto-recovered. No approval or remediation needed.")
            return

        # 3. Adversarial Reviewer Audit
        print("\n[PHASE 2: ADVERSARIAL REVIEWER AUDIT]")
        review = self.reviewer.review_diagnosis(diagnosis)
        print(f">> Reviewer Verdict    : {review['verdict']}")
        for cp in review["checks_passed"]:
            print(f"   + {cp}")

        if not review["approved"]:
            print("\n[HALTED BY REVIEWER] Diagnosis challenged. Manual investigation required.")
            return

        # 4. Human Approval Gate
        print("\n[PHASE 3: HUMAN-IN-THE-LOOP APPROVAL]")
        proposed_action = {
            "action": diagnosis.action_type,
            "target": diagnosis.root_cause_service,
            "detail": diagnosis.recommended_action
        }
        decision = self.approval_gate.request_approval(diagnosis, proposed_action)

        if not decision.approved:
            print(f"\n[REMEDIATION REJECTED] Action canceled by operator. Escalated.")
            print(f"[*] Service '{alert.service_name}' alert snoozed for {int(self.cooldown_sec)}s.")
            return

        # 5. Action API Execution
        print("\n[PHASE 4: EXECUTING APPROVED REMEDIATION]")
        exec_res = self.action_mgr.execute_action(
            action_type=diagnosis.action_type,
            target_service=diagnosis.root_cause_service,
            auth_token=decision.token,
            dry_run=self.dry_run
        )
        print(f">> Result: {exec_res.get('message') or exec_res.get('error')}")

        # 6. Post-Action Recovery Verification
        print("\n[PHASE 5: RECOVERY TELEMETRY VERIFICATION]")
        verif_res = self.verifier.verify_recovery(service_name=alert.service_name, timeout_seconds=10)

        if not verif_res.get("recovered") and not self.dry_run:
            print("\n[RECOVERY FAILED] System did not stabilize. Triggering automated safety rollback...")
            self.action_mgr.rollback_last_action()
        else:
            print(f"\n✅ [INCIDENT RESOLVED] Recovery proven across consecutive metric evaluation windows.")
            self.memory.store_resolved_incident(
                incident_id=alert.alert_id,
                service=alert.service_name,
                root_cause_service=diagnosis.root_cause_service,
                failure_mode=diagnosis.failure_mode,
                proven_action=diagnosis.action_type,
                summary=diagnosis.explanation
            )
            # Reset cooldown on successful resolution
            self.last_alert_time.pop(alert.service_name, None)

        # 7. Post-Mortem Report Generation
        print("\n[PHASE 6: INCIDENT POST-MORTEM & PREVENTION]")
        report_md = IncidentReporter.generate_markdown_report(
            alert=alert,
            diagnosis=diagnosis,
            approval=decision.to_dict(),
            execution=exec_res,
            verification=verif_res,
            reviewer_audit=review
        )
        print(report_md)
        print("\n" + "=" * 80)
        print("  INCIDENT CYCLE COMPLETE. RESUMING CONTINUOUS LIVE MONITORING...")
        print("=" * 80)

    def start_monitoring(self):
        """Main continuous polling loop."""
        print("=" * 80)
        print("  AI ON-CALL ENGINEER: CONTINUOUS LIVE MONITORING DAEMON ACTIVE")
        print(f"  Monitored Services : {len(MONITORED_SERVICES)} microservices")
        print(f"  Polling Interval   : Every {self.interval} seconds (Cooldown: {int(self.cooldown_sec)}s)")
        print(f"  Approval Barrier   : {'AUTOMATED (--auto-approve)' if self.auto_approve else 'INTERACTIVE (prompts human for confirmation)'}")
        print(f"  Dry-Run Mode       : {'ENABLED' if self.dry_run else 'DISABLED (live action dispatch)'}")
        print("  Press Ctrl+C at any time to pause or activate Emergency Kill Switch.")
        print("=" * 80)

        heartbeat_counter = 0

        while True:
            try:
                incident_found = False

                for service in MONITORED_SERVICES:
                    alert = self.check_service_health(service)
                    if alert:
                        self.handle_incident(alert)
                        incident_found = True
                        break

                if not incident_found:
                    heartbeat_counter += 1
                    if heartbeat_counter % 6 == 0:  # Print heartbeat every ~30s
                        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
                        print(f"[{now_str}] [HEARTBEAT] All monitored services operating within SLA envelope. Monitoring...")

                time.sleep(self.interval)

            except KeyboardInterrupt:
                print("\n\n[PAUSED] Monitor daemon interrupted by operator.")
                choice = input("Select action: (r)esume, (k)ill-switch halt, (q)uit [resume]: ").strip().lower()
                if choice == "k":
                    print("\n[EMERGENCY KILL SWITCH ACTIVATED] Halting all operations.")
                    break
                elif choice == "q":
                    print("Exiting on-call daemon.")
                    break
                else:
                    print("Resuming monitoring...")


def main():
    parser = argparse.ArgumentParser(description="Continuous Live On-Call Monitor Daemon")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds (default: 5)")
    parser.add_argument("--threshold", type=float, default=1.0, help="Latency threshold in seconds (default: 1.0)")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve fixes in automated evaluations")
    parser.add_argument("--dry-run", action="store_true", help="Simulate fixes without mutating system state")
    args = parser.parse_args()

    daemon = OnCallMonitor(
        check_interval_sec=args.interval,
        auto_approve=args.auto_approve,
        dry_run=args.dry_run,
        threshold_sec=args.threshold
    )
    daemon.start_monitoring()


if __name__ == "__main__":
    main()
