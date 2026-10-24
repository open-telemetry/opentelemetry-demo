"""Local eval: reset -> inject -> wait -> run the agent -> compare with expected -> reset.

Only this script talks to faultctl (via subprocess). The agent never imports or calls it.
Run from the repo root:  python oncall/scripts/eval_local.py [--wait 120] [--only name,name]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from oncall.agent.run import investigate, new_run_id  # noqa: E402
from oncall.config import settings  # noqa: E402
from oncall.events import EventLog  # noqa: E402
from oncall.ledger import EvidenceLedger  # noqa: E402
from oncall.llm import LLMClient  # noqa: E402

FAULTCTL = os.getenv("FAULTCTL", r"D:\ON-Call\agent\devtools\faultctl.py")

SCENARIOS = {
    "payment_flag": {"inject": ["inject", "flag", "paymentFailure", "100%"], "service": "payment", "fault_class": "app_error", "symptom": "checkout is failing"},
    "stopped_shipping": {"inject": ["inject", "stop", "shipping"], "service": "shipping", "fault_class": "container_down", "symptom": "customers cannot complete checkout"},
    "cpu_product_catalog": {"inject": ["inject", "cpu", "product-catalog", "0.05"], "service": "product-catalog", "fault_class": "cpu_throttle", "symptom": "the shop is slow"},
}


def faultctl(*args: str) -> None:
    result = subprocess.run([sys.executable, FAULTCTL, *args], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"faultctl {' '.join(args)} failed: {result.stderr.strip()[:200]}")


def run_scenario(name: str, scenario: dict, wait: int, settle: int) -> dict:
    row = {"scenario": name, "expected": f"{scenario['service']}/{scenario['fault_class']}", "got": "-", "confidence": "-", "escalate": "-", "evidence": "-", "result": "ERROR"}
    try:
        faultctl("reset")
        time.sleep(settle)
        faultctl(*scenario["inject"])
        print(f"[{name}] injected, waiting {wait}s", flush=True)
        time.sleep(wait)
        events = EventLog(new_run_id(), settings.RUNS_DIR)
        diagnosis, _ = investigate(scenario["symptom"], LLMClient(), EvidenceLedger(), events)
        row.update(
            got=f"{diagnosis.root_cause_service}/{diagnosis.fault_class}",
            confidence=f"{diagnosis.confidence:.2f}",
            escalate=str(diagnosis.escalate),
            evidence=str(len(diagnosis.evidence_ids)),
            result="PASS" if (diagnosis.root_cause_service, diagnosis.fault_class) == (scenario["service"], scenario["fault_class"]) else "FAIL",
        )
    except Exception as exc:
        row["got"] = f"{type(exc).__name__}: {str(exc)[:60]}"
    finally:
        faultctl("reset")
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", type=int, default=120)
    parser.add_argument("--settle", type=int, default=300, help="seconds to let old faults leave the metric window")
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    names = [n for n in SCENARIOS if not args.only or n in args.only.split(",")]
    rows = [run_scenario(n, SCENARIOS[n], args.wait, args.settle) for n in names]
    columns = ["scenario", "expected", "got", "confidence", "escalate", "evidence", "result"]
    print("\n" + " | ".join(f"{c:<28}" if c in ("scenario", "expected", "got") else f"{c:<10}" for c in columns))
    for row in rows:
        print(" | ".join(f"{row[c]:<28}" if c in ("scenario", "expected", "got") else f"{row[c]:<10}" for c in columns))


if __name__ == "__main__":
    main()
