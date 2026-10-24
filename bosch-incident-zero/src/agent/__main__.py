"""Run one investigation from the command line.

    python -m src.agent --alert "Error rate above 5% on frontend"
    python -m src.agent --alert "..." --approve-via chat   # approve in the local chat UI
    python -m src.agent --demo                  # end-to-end judge demonstration
    python -m src.agent --tools-only            # live smoke test of every tool, no LLM needed

Every action needs a human decision at the prompt (or in the chat UI), on every attempt. Dry run is the
default. A live action that measurably fails to recover the symptom is rolled back and the incident is
re-investigated, up to --max-attempts times; report.json is written only when the loop has ended.
"""
from __future__ import annotations

import argparse
import json
import sys

from ..config import Settings
from ..events import EventLog
from .agent import MAX_TOOL_CALLS, IncidentAgent
from .llm import LLMConfigError, session_factory
from .presenter import format_incident_brief
from .tools import TOPOLOGY, ToolBox, ToolContext
from ..approval.loop import MAX_ATTEMPTS_CAP, configured_max_attempts, run_remediation_loop


def _tools_smoke(box: ToolBox) -> int:
    overview = box.execute("system_overview", {"window_minutes": 5})
    services = [r["service"] for r in overview.get("data", {}).get("services", []) if r["service"] in TOPOLOGY]
    target = services[0] if services else "frontend"
    calls = [
        ("system_overview", {"window_minutes": 5}),
        ("get_service_metrics", {"service": target}),
        ("dependency_map", {"service": target}),
        ("search_traces", {"service": "frontend", "errors_only": False, "limit": 3}),
        ("search_logs", {"level": "warn", "limit": 5}),
        ("container_health", {}),
        ("deploy_history", {}),
    ]
    first_trace = None
    for name, args in calls:
        res = overview if name == "system_overview" else box.execute(name, args)
        if name == "search_traces":
            first_trace = next((e["ref"] for e in res.get("evidence", []) if e["kind"] == "trace"), None)
        print(f"{name:20s} {res['status']:18s} {res['summary'][:110]}")
    if first_trace:
        res = box.execute("get_trace", {"trace_id": first_trace})
        print(f"{'get_trace':20s} {res['status']:18s} {res['summary'][:110]}")
    return 0


LLM_ESCALATION = ("ESCALATED TO HUMAN: the LLM is not configured ({error}). No diagnosis was made and "
                  "no action was taken. Set LLM_PROVIDER/LLM_API_KEY or investigate manually.")


def print_paths(settings: Settings, events: EventLog, incident_id: str) -> None:
    out = settings.resolve_path(settings.report_output_dir) / incident_id
    print(f"Report      : {out / 'report.json'}", flush=True)
    print(f"Report (md) : {out / 'report.md'}", flush=True)
    print(f"Run log     : {events.run_log_path}", flush=True)
    print(f"Audit log   : {events.audit_log_path}", flush=True)


def main(argv=None, approval_callback=None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.agent", description="Bosch Incident Zero Investigation Agent")
    p.add_argument("--alert", help="Alert text that starts the investigation.")
    p.add_argument("--demo", action="store_true", help="Run the turnkey end-to-end demonstration scenario.")
    p.add_argument("--incident-id", help="Explicit incident ID to assign.")
    p.add_argument("--max-tool-calls", type=int, default=MAX_TOOL_CALLS)
    p.add_argument("--tools-only", action="store_true", help="Run every tool once against the live stack.")
    p.add_argument("--approve-via", choices=("cli", "chat"), default="cli",
                   help="Where the human approves or rejects the proposed action (default: cli prompt).")
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True,
                   help="Record the action without calling the Action API (default). A live run also "
                        "needs DRY_RUN_MODE=false and a configured Action API.")
    p.add_argument("--quiet", action="store_true",
                   help="Do not echo run events to the terminal (they are still written to the logs).")
    p.add_argument("--max-attempts", type=int, default=None,
                   help=f"Remediation attempts before escalating (default REMEDIATION_MAX_ATTEMPTS or 3, "
                        f"capped at {MAX_ATTEMPTS_CAP}). Only a measured non-recovery on a live backend retries.")
    p.add_argument("--raw", action="store_true", help="Print raw JSON outputs instead of the human-readable incident brief.")
    args = p.parse_args(argv)

    settings = Settings()
    ctx = ToolContext(settings)
    box = ToolBox(ctx)

    if args.tools_only:
        return _tools_smoke(box)

    alert_text = args.alert
    if args.demo:
        alert_text = alert_text or "High latency and checkout degradation on frontend with cascading downstream calls"
        print("\n" + "=" * 78)
        print(" STARTING BOSCH INCIDENT ZERO END-TO-END DEMO")
        print("=" * 78)
        print(f" Alert: '{alert_text}'\n")

    if not alert_text:
        p.error("--alert or --demo is required (or use --tools-only)")

    out = settings.resolve_path(settings.report_output_dir)
    events = EventLog.from_settings(settings, echo=not args.quiet)
    print(f"Audit log: {events.audit_log_path}", flush=True)
    max_attempts = configured_max_attempts(settings) if args.max_attempts is None else args.max_attempts
    try:
        agent = IncidentAgent(box, session_factory(), max_tool_calls=args.max_tool_calls, events=events)
    except LLMConfigError as e:
        print(LLM_ESCALATION.format(error=e), file=sys.stderr, flush=True)
        return 2

    def investigate(incident_id, prior_attempts):
        label = "Re-investigating" if prior_attempts else "Initiating multi-signal observability investigation"
        print(f"{label}...", flush=True)
        t = agent.run(alert_text, incident_id=incident_id or args.incident_id, prior_attempts=prior_attempts)
        print(f"Completed {len(t.tool_calls)} tool calls across Prometheus, Jaeger, OpenSearch, and Docker.",
              flush=True)
        return t

    channel = "chat_ui" if args.approve_via == "chat" else "cli"
    print(f"\nRemediation loop (dry run: {args.dry_run}, approval via: {channel}, "
          f"max attempts: {max_attempts}):", flush=True)
    try:
        outcome = run_remediation_loop(
            alert_text,
            settings=settings,
            investigate=investigate,
            max_attempts=max_attempts,
            approval_callback=approval_callback,
            approval_channel=channel,
            dry_run=args.dry_run,
            ctx=ctx,
            events=events,
            open_browser=channel == "chat_ui" and sys.stdin.isatty(),
        )
    except LLMConfigError as e:
        print(LLM_ESCALATION.format(error=e), file=sys.stderr, flush=True)
        return 2
    t = outcome.transcript
    print(f"Pipeline outcome: {outcome.status} ({outcome.reason})", flush=True)
    print(f"Final status: {outcome.final_status} after {len(outcome.attempts)} attempt(s) "
          f"({outcome.final_reason})", flush=True)

    if args.raw:
        print("\n--- GATE ---")
        print(json.dumps(t.gate, indent=2))
        print("\n--- REPORT ---")
        print(json.dumps(t.report, indent=2))
        print(f"schema valid: {t.report_schema_valid} {t.report_schema_errors or ''}")
        if t.errors:
            print("errors:", t.errors)
        print(f"saved to {out / t.incident_id}")
    else:
        brief = format_incident_brief(
            t,
            action=outcome.action,
            output_dir=out,
            audit_log_path=settings.resolve_path(settings.audit_log_path),
            verification=outcome.verification,
            timeline=outcome.timeline,
            events=events,
        )
        print(brief, flush=True)
    print_paths(settings, events, t.incident_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
