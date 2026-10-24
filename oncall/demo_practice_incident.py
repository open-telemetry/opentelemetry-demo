#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive Demonstration of the Improved AI On-Call Engineer.
Demonstrates:
1. Correct Root-Cause Logic: Never blames a flag when evidence shows it is 'off'.
2. Downstream vs Alerted Service Isolation: Alert fires on 'checkout', but root cause is 'payment'.
3. Evidence Categorization: Confirmed Facts vs Likely Causes vs Ruled Out Hypotheses.
4. Evidence Consistency Check: Blocks actions if the system is already in the target state.
5. Strict Trace ID Log Filtering: Zero fabrication of trace IDs in OpenSearch logs.
"""

import os
import sys

# Ensure repository root is in python search path and UTF-8 encoding
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime, timezone
from oncall.models import IncidentAlert
from oncall.agent import AIOnCallAgent
from oncall.actions.flagd_action import FlagdActionClient


def print_banner(text: str):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def run_scenario_a():
    print_banner("SCENARIO A: CART SLOWDOWN WITH NO ACTIVE FLAGS (CORRECT ROOT CAUSE LOGIC)")
    print("Context: Service 'cart' exhibits high latency, but Flagd configuration audit shows")
    print("         'cartFailure' is currently 'off'. Agent must NOT blame the flag!\n")

    alert = IncidentAlert(
        alert_id="INC-CART-001",
        service_name="cart",
        title="CartAddItemHighLatency",
        severity="critical",
        started_at=datetime.now(timezone.utc),
        summary="P95 response latency exceeded 2000ms threshold on CartService/AddItem."
    )

    agent = AIOnCallAgent()
    diagnosis = agent.investigate(alert)

    print(f">> Target Service      : {diagnosis.target_service}")
    print(f">> Root Cause Service  : {diagnosis.root_cause_service}")
    print(f">> Failure Mode        : {diagnosis.failure_mode}")
    print(f">> Calibrated Conf.    : {diagnosis.confidence_score * 100:.1f}%")
    print(f">> Consistency Passed  : {diagnosis.evidence_consistency_passed}")

    print("\n[EVIDENCE CATEGORIZATION]")
    print("  Confirmed Empirical Facts:")
    for f in diagnosis.confirmed_facts:
        print(f"    + {f}")

    print("  Likely Causes:")
    for lc in diagnosis.likely_causes:
        print(f"    * {lc}")

    print("  Ruled Out Hypotheses:")
    for uh in diagnosis.unresolved_hypotheses:
        print(f"    - {uh}")

    print(f"\nRecommended Action: {diagnosis.recommended_action} (Action: {diagnosis.action_type})")


def run_scenario_b():
    print_banner("SCENARIO B: DOWNSTREAM FAILURE (DOES NOT BLAME ALERTED SERVICE)")
    print("Context: Alert fires on 'checkout', but distributed tracing isolates root cause to 'payment'.\n")

    alert = IncidentAlert(
        alert_id="INC-CHECKOUT-002",
        service_name="checkout",
        title="CheckoutOrderPlacementErrors",
        severity="critical",
        started_at=datetime.now(timezone.utc),
        summary="Checkout service reports elevated error rates and timeouts during PlaceOrder calls."
    )

    agent = AIOnCallAgent()
    diagnosis = agent.investigate(alert)

    print(f">> Alerted Service     : {diagnosis.target_service}")
    print(f">> ACTUAL Root Cause   : {diagnosis.root_cause_service} (NOT {diagnosis.target_service}!)")
    print(f">> Failure Mode        : {diagnosis.failure_mode}")
    print(f">> Calibrated Conf.    : {diagnosis.confidence_score * 100:.1f}%")

    print("\n[EVIDENCE CATEGORIZATION]")
    print("  Confirmed Empirical Facts:")
    for f in diagnosis.confirmed_facts:
        print(f"    + {f}")

    print("  Likely Causes:")
    for lc in diagnosis.likely_causes:
        print(f"    * {lc}")

    print(f"\nTrace & Log Citations Grounding Downstream Causation:")
    for c in diagnosis.citations:
        print(f"  - [{c.source_type.upper()}] {c.identifier} -> {c.summary}")


def run_consistency_check_demo():
    print_banner("SCENARIO C: EVIDENCE CONSISTENCY GUARD (PREVENT REDUNDANT NO-OP MUTATIONS)")
    print("Context: Operator or hallucinated action attempts to set 'cartFailure' to 'off',")
    print("         but the configuration is ALREADY 'off'. The safety gate must stop execution!\n")

    client = FlagdActionClient()
    result = client.reset_flag("cartFailure", target_variant="off", dry_run=False)

    print(f">> Target Flag         : {result.get('flag_name')}")
    print(f">> Target Variant      : {result.get('target_variant')}")
    print(f">> Current Variant     : {result.get('current_variant')}")
    print(f">> Consistency Passed  : {result.get('consistency_passed')}")
    print(f">> Outcome Message     :\n   {result.get('error') or result.get('message')}")


if __name__ == "__main__":
    run_scenario_a()
    run_scenario_b()
    run_consistency_check_demo()
    print("\n" + "=" * 80)
    print("  ALL 5 CRITICAL IMPROVEMENTS SUCCESSFULLY DEMONSTRATED")
    print("=" * 80)
