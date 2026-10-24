"""Turnkey demonstration runner for Bosch Incident Zero.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --scenario recommendation
    python scripts/run_demo.py --interactive
    python scripts/run_demo.py --test-kill-switch
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure package root is on sys.path
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.config import Settings
from src.agent.agent import IncidentAgent
from src.agent.llm import session_factory
from src.agent.presenter import format_incident_brief
from src.agent.tools import ToolBox, ToolContext
from src.approval.pipeline import execute_safety_pipeline
from src.remediation.kill_switch import KillSwitch


SCENARIOS = {
    "checkout": "High latency and checkout degradation on frontend with cascading downstream calls",
    "recommendation": "Elevated p95 latency on recommendation service ProductCatalog ListProducts calls",
    "payment": "Dependency failure on payment service RPC gateway timeout",
    "cart": "Memory pressure and growing connection backlog on valkey-cart",
}


def run_demo(
    scenario_key: str = "checkout",
    interactive: bool = False,
    test_kill_switch: bool = False,
    custom_alert: str | None = None,
) -> int:
    settings = Settings()
    ctx = ToolContext(settings)
    box = ToolBox(ctx)
    out_dir = Path(settings.report_output_dir)
    if not out_dir.is_absolute():
        out_dir = settings.root_dir / out_dir

    alert_text = custom_alert or SCENARIOS.get(scenario_key, SCENARIOS["checkout"])

    print("=" * 78)
    print(" BOSCH INCIDENT ZERO -- END-TO-END DEMONSTRATION RUNNER")
    print("=" * 78)
    print(f" Scenario Target : {scenario_key}")
    print(f" Ingested Alert  : '{alert_text}'")
    print(f" Mode            : {'Interactive Approval' if interactive else 'Automated Demo'}")
    if test_kill_switch:
        print(" Kill-Switch Test: ENGAGED (Verifying fail-closed emergency stop)")
    print("=" * 78)

    # 1. Engage kill switch if requested for demonstration
    ks = KillSwitch(sentinel_path=settings.kill_switch_file, env_var="KILL_SWITCH_ENABLED")
    if test_kill_switch:
        ks.engage_sentinel()

    try:
        # 2. Run agent investigation
        print("\n[PHASE 1] Investigating multi-signal telemetry (Metrics, Traces, Logs, Docker)...")
        agent = IncidentAgent(box, session_factory(), max_tool_calls=12, output_dir=out_dir)
        transcript = agent.run(alert_text)

        print(f"[OK] Completed {len(transcript.tool_calls)} tool calls against the live observability stack.")

        # 3. Safety Controls & Action Pipeline
        print("\n[PHASE 2] Evaluating safety controls & remediation proposal...")
        auto_approve = not interactive and not test_kill_switch
        action = execute_safety_pipeline(
            transcript,
            settings=settings,
            interactive=interactive,
            auto_approve=auto_approve,
            ctx=ctx,
        )

        # 4. Present Incident Brief
        brief = format_incident_brief(
            transcript,
            action=action,
            output_dir=out_dir,
            audit_log_path=settings.audit_log_path,
        )
        print(brief)

        print("[OK] Demonstration run completed successfully.")
        return 0

    finally:
        if test_kill_switch:
            ks.disengage_sentinel()
            print("[CLEANUP] Disengaged test kill-switch sentinel.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bosch Incident Zero Demo Runner")
    p.add_argument("--scenario", choices=list(SCENARIOS.keys()), default="checkout", help="Preconfigured incident scenario")
    p.add_argument("--alert", help="Custom incident alert string")
    p.add_argument("--interactive", action="store_true", help="Prompt operator interactively for human approval")
    p.add_argument("--test-kill-switch", action="store_true", help="Demonstrate emergency kill-switch blocking action")
    args = p.parse_args(argv)

    return run_demo(
        scenario_key=args.scenario,
        interactive=args.interactive,
        test_kill_switch=args.test_kill_switch,
        custom_alert=args.alert,
    )


if __name__ == "__main__":
    sys.exit(main())

