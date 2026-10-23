"""Run one investigation from the command line.

    python -m src.agent --alert "Error rate above 5% on frontend" [--max-tool-calls 12]
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
from .tools import TOPOLOGY, ToolBox, ToolContext


def _tools_smoke(box: ToolBox) -> int:
    overview = box.execute("system_overview", {"window_minutes": 5})
    services = [r["service"] for r in overview.get("data", {}).get("services", []) if r["service"] in TOPOLOGY]
    target = services[0] if services else "frontend"
    calls = [("system_overview", {"window_minutes": 5}), ("get_service_metrics", {"service": target}),
             ("dependency_map", {"service": target}), ("search_traces", {"service": "frontend", "errors_only": False, "limit": 3}),
             ("search_logs", {"level": "warn", "limit": 5}), ("container_health", {}), ("deploy_history", {})]
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
    p = argparse.ArgumentParser(prog="python -m src.agent")
    p.add_argument("--alert", help="Alert text that starts the investigation.")
    p.add_argument("--incident-id")
    p.add_argument("--max-tool-calls", type=int, default=MAX_TOOL_CALLS)
    p.add_argument("--tools-only", action="store_true", help="Run every tool once against the live stack.")
    args = p.parse_args(argv)

    settings = Settings()
    box = ToolBox(ToolContext(settings))
    if args.tools_only:
        return _tools_smoke(box)
    if not args.alert:
        p.error("--alert is required (or use --tools-only)")
    try:
        factory = session_factory()
    except LLMConfigError as e:
        print(f"LLM not configured: {e}", file=sys.stderr)
        return 2
    out = Path(settings.report_output_dir)
    if not out.is_absolute():
        out = settings.root_dir / out
    agent = IncidentAgent(box, factory, max_tool_calls=args.max_tool_calls, output_dir=out)
    t = agent.run(args.alert, incident_id=args.incident_id)
    print(f"tool calls: {len(t.tool_calls)}  (cap hit: {t.step_cap_hit})")
    for c in t.tool_calls:
        print(f"  {c['n']:2d}. {c['tool']}({json.dumps(c['arguments'])}) -> {c['result']['status']}: "
              f"{c['result']['summary'][:90]}")
    print("gate:", json.dumps(t.gate))
    print("report:", json.dumps(t.report, indent=2))
    print(f"schema valid: {t.report_schema_valid} {t.report_schema_errors or ''}")
    if t.errors:
        print("errors:", t.errors)
    print(f"saved to {out / t.incident_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
