"""Command line entry point: python -m oncall.main <command> ..."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime

from oncall.models import Alert


def _manual_alert(service: str | None, description: str) -> Alert:
    now = datetime.now(UTC)
    return {
        "id": f"manual-{now.strftime('%Y%m%dT%H%M%S')}",
        "ts": now.isoformat(),
        "service": service,
        "signal": "manual",
        "value": None,
        "threshold": None,
        "description": description,
        "source": "manual",
    }


def cmd_investigate(args: argparse.Namespace) -> int:
    if args.offline:
        os.environ["TELEMETRY_BACKEND"] = "offline"
        os.environ["OFFLINE_SCENARIO"] = args.offline

    from oncall.agent.loop import investigate_and_diagnose
    from oncall.agent.runlog import RunLog
    from oncall.config import load_settings
    from oncall.report.output import report_run

    runlog = RunLog(runs_dir=load_settings().RUNS_DIR)
    alert = _manual_alert(args.service, args.description)
    result = investigate_and_diagnose(alert, runlog=runlog)
    json_path, md_path = report_run(alert, result["diagnosis"], runlog)

    print(f"run_id:  {result['run_id']}")
    print(f"stopped: {result['stopped']} after {result['steps']} steps")
    print("tools:")
    for i, call in enumerate(runlog.events("tool_call"), 1):
        print(f"  {i}. {call['name']}({call['args']})")
    print(f"summary:\n{result['summary']}")
    print(f"diagnosis:\n{json.dumps(result['diagnosis'], indent=2)}")
    print(f"run log: {runlog.path}")
    print(f"report:  {json_path} + {md_path.name}")
    print(f"tokens:  {runlog.token_usage()}")
    return 0 if result["stopped"] in ("finish", "max_steps") else 1


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(prog="python -m oncall.main")
    sub = parser.add_subparsers(dest="command", required=True)

    inv = sub.add_parser("investigate", help="investigate an alert")
    inv.add_argument("--service", default=None)
    inv.add_argument("--description", required=True)
    inv.add_argument("--offline", metavar="SCENARIO", default=None)
    inv.set_defaults(func=cmd_investigate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
