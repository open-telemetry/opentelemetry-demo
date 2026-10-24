"""Live smoke test: call every agent tool once against the running demo.

Not part of CI (it needs the demo up). Run from anywhere:
    python scripts/smoke_live.py
Prints a markdown table and exits 1 if any check fails.

Checks per call: ok, evidence present (only where a healthy demo always has
some), no "unknown"/"unattributed" evidence ids, unique ids, no excluded service
or feature-flag text in what the LLM would see, summary within the contract,
and latency data for latency_p95.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oncall.platform.containers
import oncall.platform.deploys  # noqa: F401
from oncall.models import FLAG_PATTERN, MAX_SUMMARY_CHARS, llm_view
from oncall.safety.exclusions import EXCLUDED_SERVICES
from oncall.tools import TOOLS

# (tool, args, evidence required on a healthy demo)
CALLS = [
    ("get_metrics", {"metric": "error_rate"}, True),
    ("get_metrics", {"metric": "latency_p95"}, True),
    ("get_metrics", {"metric": "rps"}, True),
    ("get_metrics", {"metric": "top_errors"}, True),
    ("search_logs", {"level": "warn"}, True),
    ("search_traces", {"service": "frontend"}, False),
    ("search_traces", {"service": "checkout", "only_errors": False}, False),
    ("container_health", {}, True),
    ("deploy_history", {}, False),
]
BAD_ID_WORDS = ("unknown", "unattributed")


def check(name: str, args: dict, needs_evidence: bool) -> dict:
    started = time.time()
    result = TOOLS[name](**args)
    seconds = time.time() - started
    ids = [e["id"] for e in result["evidence"]]
    seen = json.dumps(llm_view(result)).replace("FLAGGED", "")
    leaks = [s for s in EXCLUDED_SERVICES if s in seen]
    if FLAG_PATTERN.search(seen):
        leaks.append("feature-flag text")
    failures = []
    if not result["ok"]:
        failures.append(f"error: {result['error']}")
    if needs_evidence and not ids:
        failures.append("no evidence")
    if any(word in i for i in ids for word in BAD_ID_WORDS):
        failures.append("unknown/unattributed id")
    if len(ids) != len(set(ids)):
        failures.append("duplicate ids")
    if leaks:
        failures.append("leaks " + ", ".join(leaks))
    if len(result["summary"]) > MAX_SUMMARY_CHARS:
        failures.append("summary too long")
    if args.get("metric") == "latency_p95" and not ids:
        failures.append("no latency data")
    return {
        "call": f"{name} {json.dumps(args)}",
        "ok": result["ok"],
        "evidence": len(ids),
        "summary_chars": len(result["summary"]),
        "seconds": round(seconds, 1),
        "failures": failures,
        "first_line": result["summary"].splitlines()[0][:80]
        if result["summary"]
        else "",
    }


def main() -> int:
    rows = [check(*call) for call in CALLS]
    print("| call | ok | evidence | summary chars | s | result | first summary line |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        verdict = "PASS" if not r["failures"] else "FAIL: " + "; ".join(r["failures"])
        print(
            f"| {r['call']} | {r['ok']} | {r['evidence']} | {r['summary_chars']} "
            f"| {r['seconds']} | {verdict} | {r['first_line']} |"
        )
    failed = sum(1 for r in rows if r["failures"])
    print(f"\n{len(rows) - failed}/{len(rows)} calls passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
