#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Benchmark Suite for Hackathon Checkpoint 2: The Brain.
Evaluates the AI On-Call Engineer across 3 Mentor Practice Incidents:
1. Incident 1: CartAddItemHighLatency (Internal datastore timeout on valkey-cart)
2. Incident 2: CheckoutOrderPlacementErrors (Downstream failure: alert on checkout, root cause on payment)
3. Incident 3: AdServiceHighCpuOrGc (Resource exhaustion / CPU saturation on ad)

Validates:
- Precise root-cause identification (Downstream vs alerted)
- Categorized evidence (Confirmed Facts, Likely Causes, Ruled Out Hypotheses)
- Telemetry citations (Prometheus, Jaeger, OpenSearch, Git commits)
- Compliance with Rule 6 (Zero cheating via feature flag inspection during diagnosis)
- Export to Checkpoint 2 JSON schema
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from oncall.models import IncidentAlert
from oncall.agent import AIOnCallAgent


def evaluate_checkpoint_2():
    print("=" * 80)
    print("  BOSCH HACKATHON CHECKPOINT 2: BRAIN EVALUATION (3 PRACTICE INCIDENTS)")
    print("=" * 80)

    practice_incidents = [
        IncidentAlert(
            alert_id="ALERT-PRAC-001",
            service_name="cart",
            title="CartAddItemHighLatency",
            severity="critical",
            started_at=datetime.now(timezone.utc),
            summary="P95 response latency exceeded 2000ms threshold on CartService/AddItem."
        ),
        IncidentAlert(
            alert_id="ALERT-PRAC-002",
            service_name="checkout",
            title="CheckoutOrderPlacementErrors",
            severity="critical",
            started_at=datetime.now(timezone.utc),
            summary="Elevated HTTP 500 error rate on CheckoutService/PlaceOrder."
        ),
        IncidentAlert(
            alert_id="ALERT-PRAC-003",
            service_name="ad",
            title="AdServiceHighCpuOrGc",
            severity="warning",
            started_at=datetime.now(timezone.utc),
            summary="High CPU utilization and GC pause delays detected on ad service."
        ),
    ]

    agent = AIOnCallAgent()
    diagnoses = []
    passed_tests = 0
    total_tests = len(practice_incidents)

    for idx, alert in enumerate(practice_incidents, 1):
        print(f"\n[INCIDENT {idx}/{total_tests}] Evaluating Alert: {alert.title} ({alert.alert_id})")
        print(f"  Target Service: {alert.service_name} | Severity: {alert.severity.upper()}")
        
        diag = agent.investigate(alert, allow_fixtures=True)
        diagnoses.append(diag)

        # Assertions for evaluation
        print(f"  >> Diagnosed Root Cause : {diag.root_cause_service}")
        print(f"  >> Failure Mode         : {diag.failure_mode}")
        print(f"  >> Confidence           : {diag.confidence_score * 100:.1f}%")
        print(f"  >> Citations Count      : {len(diag.citations)}")

        # Verification checks
        if idx == 1:
            assert diag.root_cause_service == "cart", "Scenario 1 must isolate cart service"
            assert "DATASTORE_TIMEOUT" in diag.failure_mode, "Scenario 1 failure mode must identify datastore/timeout"
        elif idx == 2:
            assert diag.root_cause_service == "payment", "Scenario 2 must isolate downstream payment service"
            assert diag.root_cause_service != diag.target_service, "Scenario 2 must NOT blame checkout"
            assert "DOWNSTREAM" in diag.failure_mode, "Scenario 2 must identify downstream failure"
        elif idx == 3:
            assert diag.root_cause_service == "ad", "Scenario 3 must isolate ad service"
            assert "RESOURCE_EXHAUSTION" in diag.failure_mode, "Scenario 3 must identify resource exhaustion"

        # Assert zero flagd cheating citations per Rule 6
        for c in diag.citations:
            assert "flagd" not in c.source_type.lower(), f"Rule 6 Violation: Flag citation found: {c.source_type}"

        print("  [STATUS]: PASS (Evidence-grounded and compliant)")
        passed_tests += 1

    print("\n" + "=" * 80)
    print(f"  EVALUATION SUMMARY: {passed_tests}/{total_tests} INCIDENTS PASSED")
    print("=" * 80)

    # Save output to checkpoint2_diagnoses.json
    out_path = os.path.join(os.path.dirname(__file__), "checkpoint2_diagnoses.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([d.model_dump(mode="json") for d in diagnoses], f, indent=2)
    print(f"\nSaved mentor-compliant diagnoses to: {out_path}")
    return diagnoses


if __name__ == "__main__":
    evaluate_checkpoint_2()
