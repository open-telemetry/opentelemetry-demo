"""Run one investigation from the command line.

    python -m src.agent --alert "Error rate above 5% on frontend"
    python -m src.agent --demo                  # end-to-end judge demonstration
    python -m src.agent --tools-only            # live smoke test of every tool, no LLM needed
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config import Settings
from .agent import MAX_TOOL_CALLS, IncidentAgent
from .llm import LLMConfigError, session_factory
from .presenter import format_incident_brief
from .tools import TOPOLOGY, ToolBox, ToolContext
from ..approval.pipeline import execute_safety_pipeline


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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.agent", description="Bosch Incident Zero Investigation Agent")
    p.add_argument("--alert", help="Alert text that starts the investigation.")
    p.add_argument("--demo", action="store_true", help="Run the turnkey end-to-end demonstration scenario.")
    p.add_argument("--incident-id", help="Explicit incident ID to assign.")
    p.add_argument("--max-tool-calls", type=int, default=MAX_TOOL_CALLS)
    p.add_argument("--tools-only", action="store_true", help="Run every tool once against the live stack.")
    p.add_argument("--auto-approve", action="store_true", help="Automatically approve the proposed dry-run remediation action.")
    p.add_argument("--interactive", action="store_true", help="Interactively prompt operator for human approval.")
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

    try:
        factory = session_factory()
    except LLMConfigError as e:
        print(f"LLM not configured: {e}", file=sys.stderr)
        return 2

    out = Path(settings.report_output_dir)
    if not out.is_absolute():
        out = settings.root_dir / out

    agent = IncidentAgent(box, factory, max_tool_calls=args.max_tool_calls, output_dir=out)
    print("Initiating multi-signal observability investigation...")
    t = agent.run(alert_text, incident_id=args.incident_id)

    print(f"Completed {len(t.tool_calls)} tool calls across Prometheus, Jaeger, OpenSearch, and Docker:")
    for c in t.tool_calls:
        print(f"  {c['n']:2d}. {c['tool']}({json.dumps(c['arguments'])}) -> {c['result']['status']}: "
              f"{c['result']['summary'][:80]}")

    # Safety & Remediation Governance Pipeline
    auto_approve = args.auto_approve or (args.demo and not args.interactive)
    action = execute_safety_pipeline(
        t,
        settings=settings,
        interactive=args.interactive,
        auto_approve=auto_approve,
        ctx=ctx,
    )

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
            action=action,
            output_dir=out,
            audit_log_path=settings.audit_log_path,
        )
        print(brief)

    return 0


if __name__ == "__main__":
    sys.exit(main())
