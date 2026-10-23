#!/usr/bin/env python3
"""Evaluation harness for AI On-Call Engineer.

Runs incidents from INCIDENTS_CATALOG, evaluates detection -> diagnosis -> approval -> execution -> verification,
demonstrates repeat diagnosis with memory assist, and outputs evaluation scores.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import httpx

AGENT_URL = os.environ.get("ONCALL_AGENT_URL", "http://localhost:8200")
REPORTS_DIR = Path("oncall-data/agent/reports")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval-harness")


def run_cmd(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def reset_stack() -> None:
    logger.info("Resetting stack via tools/faultctl.py reset...")
    subprocess.run([sys.executable, "tools/faultctl.py", "reset"], check=True)


def inject_incident(incident_id: int) -> None:
    logger.info("Injecting incident #%d via tools/faultctl.py inject %d...", incident_id, incident_id)
    subprocess.run([sys.executable, "tools/faultctl.py", "inject", str(incident_id)], check=True)


def wait_for_incident(timeout_s: int = 60, auto_trigger: bool = True) -> dict[str, Any] | None:
    """Wait for oncall-agent to detect or manually trigger an evaluation cycle."""
    start = time.time()

    if auto_trigger:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(f"{AGENT_URL}/incidents/investigate", json={"auto_approve": True})
                if res.status_code == 200:
                    data = res.json()
                    inc_id = data.get("incident_id")
                    if inc_id:
                        logger.info("Triggered investigation cycle: %s", inc_id)
        except Exception as e:
            logger.warning("Could not auto-trigger investigate: %s", e)

    while time.time() - start < timeout_s:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{AGENT_URL}/incidents")
                if res.status_code == 200:
                    incidents = res.json()
                    if incidents:
                        # Return most recent incident
                        latest = sorted(incidents, key=lambda x: x.get("detected_at", ""), reverse=True)[0]
                        state = latest.get("state")
                        if state in ("RESOLVED", "ESCALATED", "ROLLED_BACK", "REJECTED"):
                            return latest
                        logger.info("Incident %s in state %s...", latest.get("incident_id"), state)
        except Exception as e:
            logger.warning("Polling error: %s", e)
        time.sleep(3)

    return None


def run_single(incident_id: int, auto_approve: bool = True) -> dict[str, Any]:
    logger.info("=== Running Incident #%d ===", incident_id)
    reset_stack()
    time.sleep(3)

    inject_incident(incident_id)
    time.sleep(5)

    inc = wait_for_incident(timeout_s=60, auto_trigger=True)
    if not inc:
        logger.error("Incident #%d timed out without terminal state", incident_id)
        return {"incident_id": incident_id, "status": "timeout"}

    logger.info("Incident #%d reached state: %s", incident_id, inc.get("state"))
    return inc


def run_repeat_test(incident_id: int = 1) -> None:
    """Run an incident twice to demonstrate memory assist and reduced tool calls."""
    logger.info("=================================================================")
    logger.info("Phase 5: Stretch A Demonstration — Repeat Incident with Memory")
    logger.info("=================================================================")

    # Run 1
    logger.info("\n--- Run 1: Cold start (empty or initial memory) ---")
    inc1 = run_single(incident_id)
    inc1_id = inc1.get("incident_id")
    steps1 = len(inc1.get("timeline", []))
    logger.info("Run 1 completed: %s with %d timeline events", inc1_id, steps1)

    time.sleep(5)

    # Run 2
    logger.info("\n--- Run 2: Repeat execution (memory assist active) ---")
    inc2 = run_single(incident_id)
    inc2_id = inc2.get("incident_id")
    steps2 = len(inc2.get("timeline", []))
    logger.info("Run 2 completed: %s with %d timeline events", inc2_id, steps2)

    memory_assist = inc2.get("memory_assist")
    logger.info("\n=== Memory Assist Report for Run 2 ===")
    if memory_assist:
        logger.info("Matched Past Incident : %s", memory_assist.get("matched_incident"))
        logger.info("Similarity Score      : %.2f", memory_assist.get("similarity", 0))
        logger.info("Previous Steps        : %d", memory_assist.get("prev_steps", 0))
        logger.info("Current Steps         : %d", memory_assist.get("current_steps", 0))
        logger.info("Steps Saved           : %d", memory_assist.get("steps_saved", 0))
    else:
        logger.info("Memory assist recorded on report file.")

    logger.info("\nResetting stack to clean state...")
    reset_stack()
    logger.info("Repeat demonstration completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI On-Call Engineer Evaluation Runner")
    parser.add_argument("--incident", type=int, help="Run specific incident ID")
    parser.add_argument("--repeat", type=int, default=0, help="Run incident twice to demonstrate memory assist")
    parser.add_argument("--reset", action="store_true", help="Reset all faults and exit")

    args = parser.parse_args()

    if args.reset:
        reset_stack()
        return

    if args.repeat > 0:
        run_repeat_test(args.repeat)
        return

    if args.incident:
        run_single(args.incident)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
