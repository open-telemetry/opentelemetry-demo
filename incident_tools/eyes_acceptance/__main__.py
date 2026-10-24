"""Explicit operator entry point; preflight never injects a practice fault."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import uuid

from incident_tools.eyes.core import Store
from .configuration import initialize, readiness, OPENAI_MODEL, OPENAI_KEY_ENV
from .practice import Practice, reset, watchdog, write_json
from .workflow import execute


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a new operator configuration directory")
    init.add_argument("--directory", required=True)
    init.add_argument("--model", default=OPENAI_MODEL)
    init.add_argument("--project", default="opentelemetry-demo")
    init.add_argument("--prometheus", default="http://localhost:9090")
    init.add_argument("--jaeger", default="http://localhost:8080")
    init.add_argument("--opensearch", default="")
    pre = commands.add_parser("preflight", help="Offline configuration check unless live/probe flags supplied")
    pre.add_argument("--config", required=True)
    pre.add_argument("--live", action="store_true", help="Read-only live F02 queries")
    pre.add_argument("--probe-model", action="store_true", help="Send an explicit model connection probe")
    run = commands.add_parser("run", help="Run one operator-authorized practice incident")
    run.add_argument("--config", required=True)
    run.add_argument("--execute-practice", action="store_true", help="Authorize a bounded shipping pause and automatic unpause")
    run.add_argument("--detect-only", action="store_true", help="No LLM required; cannot satisfy F03 acceptance")
    run.add_argument("--duration", type=int, default=240)
    run.add_argument("--baseline-seconds", type=int, default=300)
    reset_parser = commands.add_parser("reset", help="Retry reset of the exact container in an operator journal")
    reset_parser.add_argument("--journal", required=True)
    guard = commands.add_parser("_watchdog", help=argparse.SUPPRESS)
    guard.add_argument("--journal", required=True)
    args = parser.parse_args(argv)
    lock, store, previous_signal, output = None, None, None, None
    try:
        if args.command == "init":
            print(initialize(args.directory, args.model, args.project, args.prometheus,
                             args.jaeger, args.opensearch))
            print("Check the model ID and F02 endpoints. Put " + OPENAI_KEY_ENV +
                  " in the environment only.")
            return 0
        if args.command == "_watchdog":
            return watchdog(args.journal)
        if args.command == "reset":
            print(json.dumps(reset(args.journal), indent=2))
            return 0
        if args.command == "preflight":
            result, _, _, _ = readiness(args.config, args.live, args.probe_model)
            print(json.dumps(result, indent=2))
            return 0 if result["configuration_usable"] and result["model_configuration_usable"] else 2
        if not args.execute_practice:
            parser.error("run requires --execute-practice; use preflight for read-only checks")
        if not 60 <= args.duration <= 600 or not 30 <= args.baseline_seconds <= 900:
            parser.error("duration must be 60..600 and baseline-seconds 30..900")
        result, tools, settings, model = readiness(args.config, live=True, probe_model=not args.detect_only)
        root = Path(result["artifact_dir"])
        root.mkdir(parents=True, exist_ok=True)
        output = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
        output.mkdir()
        print("Run artifacts: " + str(output), flush=True)
        write_json(output / "readiness.json", result)
        if not result["configuration_usable"] or (not args.detect_only and (
                not result["model_configuration_usable"] or not result["model_probe"])):
            write_json(output / "acceptance.json", {
                "automated_checks_passed": False, "live_acceptance_complete": False,
                "injection_started": False, "failure": "READINESS_FAILED",
                "issues": result["issues"], "model_issues": result["model_issues"]})
            print("Readiness failed; no injection. See readiness.json. Missing API key is expected until supplied.")
            return 2
        candidate = root / "operator.lock"
        with candidate.open("x", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
        lock = candidate
        store = Store(output / "evidence")
        practice = Practice(output / "operator" / "practice.json",
                            tools.config.section("docker").get("project", "opentelemetry-demo"), args.duration)
        def terminate(signum, frame):
            raise KeyboardInterrupt()
        previous_signal = signal.signal(signal.SIGTERM, terminate)
        summary = execute(tools, settings, store, model, practice, output,
                          args.duration, args.baseline_seconds, args.detect_only)
        print(json.dumps({"automated_checks_passed": summary["automated_checks_passed"],
                          "live_acceptance_complete": False, "failure": summary["failure"],
                          "semantic_review": summary["semantic_review"],
                          "incident_ids": summary["incident_ids"]}, indent=2))
        return 0 if summary["automated_checks_passed"] else 2
    except (Exception, KeyboardInterrupt) as exc:
        if output:
            write_json(output / "operator_error.json", {"error_type": type(exc).__name__,
                       "note": "Inspect readiness and the operator journal; no successful completion claimed."})
        print("Eyes acceptance stopped (" + type(exc).__name__ + "). Check configuration, readiness artifacts and operator journal; no success claimed.")
        return 2
    finally:
        if previous_signal is not None:
            signal.signal(signal.SIGTERM, previous_signal)
        if store:
            store.db.close()
        if lock:
            lock.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
