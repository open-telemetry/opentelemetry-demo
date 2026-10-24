"""Turnkey demonstration runner for Bosch Incident Zero.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --scenario recommendation
    python scripts/run_demo.py --approve-via chat
    python scripts/run_demo.py --test-kill-switch
    python scripts/run_demo.py --replay incident_output/<id>/transcript.json   # no LLM call
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
from datetime import datetime
import sys
from pathlib import Path

# Ensure package root is on sys.path
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.config import Settings
from src.agent.agent import IncidentAgent
from src.agent.llm import LLMConfigError, session_factory
from src.agent.__main__ import LLM_ESCALATION, print_paths
from src.events import EventLog
from src.agent.presenter import format_incident_brief
from src.agent.tools import ToolBox, ToolContext
from src.agent.transcript import Transcript
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
    approve_via: str = "cli",
    dry_run: bool = True,
    quiet: bool = False,
    test_kill_switch: bool = False,
    custom_alert: str | None = None,
    replay: str | None = None,
    approval_callback=None,
) -> int:
    settings = Settings()
    ctx = ToolContext(settings)
    box = ToolBox(ctx)
    out_dir = settings.resolve_path(settings.report_output_dir)
    events = EventLog.from_settings(settings, echo=not quiet)

    alert_text = custom_alert or SCENARIOS.get(scenario_key, SCENARIOS["checkout"])
    recorded = load_transcript(replay) if replay else None
    if recorded is not None:
        alert_text = recorded.alert
        scenario_key = f"REPLAY of {recorded.incident_id}"
        print("#" * 78)
        print(f" REPLAY: recorded diagnosis from {replay}")
        print(" No LLM call is made. Approval is still a live human decision.")
        print("#" * 78)

    print("=" * 78)
    print(" BOSCH INCIDENT ZERO -- END-TO-END DEMONSTRATION RUNNER")
    print("=" * 78)
    print(f" Scenario Target : {scenario_key}")
    print(f" Ingested Alert  : '{alert_text}'")
    print(f" Mode            : {'DRY RUN' if dry_run else 'LIVE'}, human approval via {approve_via}")
    if test_kill_switch:
        print(" Kill-Switch Test: ENGAGED (Verifying fail-closed emergency stop)")
    print(f" Audit log       : {events.audit_log_path}")
    print("=" * 78, flush=True)

    # 1. Engage kill switch if requested for demonstration
    ks = KillSwitch(sentinel_path=settings.resolve_path(settings.kill_switch_file), env_var="KILL_SWITCH_ENABLED")
    if test_kill_switch:
        ks.engage_sentinel()

    try:
        # 2. Run agent investigation
        if recorded is not None:
            transcript = start_replay(recorded, events)
        else:
            print("\n[PHASE 1] Investigating multi-signal telemetry (Metrics, Traces, Logs, Docker)...")
            try:
                agent = IncidentAgent(box, session_factory(), max_tool_calls=12, output_dir=out_dir,
                                      events=events)
                transcript = agent.run(alert_text)
            except LLMConfigError as e:
                print(LLM_ESCALATION.format(error=e), file=sys.stderr, flush=True)
                return 2
            print(f"[OK] Completed {len(transcript.tool_calls)} tool calls against the live observability stack.")

        # 3. Safety Controls & Action Pipeline
        print("\n[PHASE 2] Evaluating safety controls & remediation proposal...")
        outcome = execute_safety_pipeline(
            transcript,
            settings=settings,
            approval_callback=approval_callback,
            approval_channel="chat_ui" if approve_via == "chat" else "cli",
            dry_run=dry_run,
            ctx=ctx,
            events=events,
            open_browser=approve_via == "chat" and sys.stdin.isatty(),
        )
        print(f"Pipeline outcome: {outcome.status} ({outcome.reason})", flush=True)

        # 4. Present Incident Brief
        brief = format_incident_brief(
            transcript,
            action=outcome.action,
            output_dir=out_dir,
            audit_log_path=settings.resolve_path(settings.audit_log_path),
            verification=outcome.verification,
            timeline=outcome.timeline,
            events=events,
        )
        print(brief, flush=True)
        print_paths(settings, events, transcript.incident_id)
        print("[OK] Demonstration run completed.", flush=True)
        return 0

    finally:
        if test_kill_switch:
            ks.disengage_sentinel()
            print("[CLEANUP] Disengaged test kill-switch sentinel.")


def load_transcript(path: str) -> Transcript:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {f.name for f in dataclasses.fields(Transcript)}
    return Transcript(**{k: v for k, v in raw.items() if k in names})


def start_replay(recorded: Transcript, events: EventLog) -> Transcript:
    original = recorded.incident_id
    replayed = dataclasses.replace(recorded, incident_id=f"REPLAY-{original}-{datetime.now():%H%M%S}")
    if isinstance(replayed.report, dict):
        replayed.report = {**replayed.report, "incident_id": replayed.incident_id}
    events.bind(replayed.incident_id)
    events.emit("ALERT_RECEIVED", f"REPLAY of recorded run {original}: {recorded.alert}",
                {"replay_of": original, "alert": recorded.alert})
    events.emit("MODEL_NOTE", "recorded diagnosis replayed; no LLM call in this run", {"replay_of": original})
    return replayed


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bosch Incident Zero Demo Runner")
    p.add_argument("--scenario", choices=list(SCENARIOS.keys()), default="checkout", help="Preconfigured incident scenario")
    p.add_argument("--alert", help="Custom incident alert string")
    p.add_argument("--approve-via", choices=("cli", "chat"), default="cli", help="Where the human approves the action")
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True, help="Record without calling the Action API (default)")
    p.add_argument("--quiet", action="store_true", help="Do not echo run events to the terminal")
    p.add_argument("--replay", metavar="PATH", help="Replay a recorded transcript.json instead of running the agent (no LLM call)")
    p.add_argument("--test-kill-switch", action="store_true", help="Demonstrate emergency kill-switch blocking action")
    args = p.parse_args(argv)

    return run_demo(
        scenario_key=args.scenario,
        approve_via=args.approve_via,
        dry_run=args.dry_run,
        quiet=args.quiet,
        test_kill_switch=args.test_kill_switch,
        custom_alert=args.alert,
        replay=args.replay,
    )


if __name__ == "__main__":
    sys.exit(main())

