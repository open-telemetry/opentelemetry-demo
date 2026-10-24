"""Run practice incidents through the agent and print a pass/fail table.

    FAULTCTL_CMD="faultctl" python -m src.agent.eval_harness incidents.json [--only ID ...]
    python -m src.agent.eval_harness incidents.json --no-inject --only ID   # incident already injected

incidents.json (kept out of the agent's reach; expected answers are only read here):
    [{"id": "practice-01",
      "inject": ["inject", "<incident name>"],      # appended to FAULTCTL_CMD
      "reset": ["reset"],
      "alert": "Error rate above 5% on frontend",   # the only text the agent sees
      "warmup_seconds": 90,
      "expected": {"service": "payment", "category": "errors_on_operation"}}]

Injection and reset go only through the organisers' faultctl. The harness never touches flagd.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Settings
from .agent import IncidentAgent
from .llm import session_factory
from .tools import ToolBox, ToolContext


def run_faultctl(args: List[str]) -> str:
    base = os.environ.get("FAULTCTL_CMD", "").strip()
    if not base:
        raise RuntimeError("FAULTCTL_CMD is not set; point it at the organisers' faultctl.")
    proc = subprocess.run([*shlex.split(base), *args], capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"faultctl {' '.join(args)} failed: {proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


def score(expected: Dict[str, Any], transcript) -> Dict[str, Any]:
    diag = transcript.diagnosis or {}
    root = diag.get("root_cause") or {}
    gate = transcript.gate or {}
    escalated = bool(gate.get("escalate", True))

    has_diagnosis = bool(root.get("service"))
    service_match = bool(has_diagnosis and root.get("service") == expected.get("service"))
    category_match = bool(has_diagnosis and (expected.get("category") is None or root.get("category") == expected.get("category")))
    diagnosis_correct = service_match and category_match

    schema_valid = bool(getattr(transcript, "report_schema_valid", False))
    invalid_cits = gate.get("invalid_citations", 0) or 0
    citations_valid = (invalid_cits == 0)

    if not has_diagnosis:
        outcome = "NO_DIAGNOSIS"
    elif escalated:
        outcome = "ESCALATED"
    elif not diagnosis_correct:
        outcome = "FAIL_DIAGNOSIS"
    elif not schema_valid:
        outcome = "FAIL_SCHEMA_INVALID"
    elif not citations_valid:
        outcome = "FAIL_INVALID_CITATIONS"
    else:
        outcome = "PASS"

    return {
        "outcome": outcome,
        "diagnosis_correct": diagnosis_correct,
        "schema_valid": schema_valid,
        "citations_valid": citations_valid,
        "escalated": escalated,
        "service_match": service_match,
        "category_match": category_match,
        "predicted_service": root.get("service"),
        "predicted_category": root.get("category"),
        "expected": expected,
        "confidence": gate.get("final_confidence"),
        "tool_calls": len(getattr(transcript, "tool_calls", []) or []),
        "invalid_citations": invalid_cits,
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.agent.eval_harness")
    p.add_argument("incidents", type=Path)
    p.add_argument("--only", nargs="*")
    p.add_argument("--no-inject", action="store_true", help="Do not call faultctl (incident already active).")
    args = p.parse_args(argv)

    if not args.incidents.exists():
        print(f"BLOCKED: Incident definition file '{args.incidents}' not found. Obtain authorized incident cases from organizers.", file=sys.stderr)
        return 2

    try:
        raw_text = args.incidents.read_text(encoding="utf-8")
        incidents = json.loads(raw_text)
    except Exception as e:
        print(f"BLOCKED: Failed to parse incident file '{args.incidents}': {e}", file=sys.stderr)
        return 2

    if not isinstance(incidents, list):
        print(f"BLOCKED: Incident file root must be a JSON array, got {type(incidents).__name__}.", file=sys.stderr)
        return 2

    if not incidents:
        print("BLOCKED: Incident file contains no incidents.", file=sys.stderr)
        return 2

    for idx, inc in enumerate(incidents):
        if not isinstance(inc, dict):
            print(f"BLOCKED: Incident at index {idx} is not an object.", file=sys.stderr)
            return 2
        missing = [k for k in ("id", "alert") if k not in inc]
        if not args.no_inject and "inject" not in inc:
            missing.append("inject")
        if missing:
            inc_id = inc.get("id", f"index {idx}")
            print(f"BLOCKED: Incident '{inc_id}' missing required keys: {', '.join(missing)}.", file=sys.stderr)
            return 2

    if args.only:
        matched = [i for i in incidents if i["id"] in args.only]
        if not matched:
            print(f"BLOCKED: --only filter matched zero incidents (requested: {', '.join(args.only)}).", file=sys.stderr)
            return 2
        incidents = matched

    if not args.no_inject and not os.environ.get("FAULTCTL_CMD", "").strip():
        print("BLOCKED: FAULTCTL_CMD is not set. Point it at the official organizer faultctl executable.", file=sys.stderr)
        return 2

    settings = Settings()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = Path(settings.report_output_dir)
    out = (out if out.is_absolute() else settings.root_dir / out) / f"eval-{stamp}"
    agent = IncidentAgent(ToolBox(ToolContext(settings)), session_factory(), output_dir=out)

    rows = []
    for inc in incidents:
        row: Dict[str, Any] = {"id": inc["id"]}
        try:
            if not args.no_inject:
                run_faultctl(inc.get("reset", ["reset"]))
                run_faultctl(inc["inject"])
                time.sleep(int(inc.get("warmup_seconds", 90)))
            t = agent.run(inc["alert"], incident_id=f"{inc['id']}-{stamp}")
            row.update(score(inc.get("expected", {}), t))
        except Exception as e:
            row.update(outcome="ERROR", error=f"{type(e).__name__}: {str(e)[:200]}")
        finally:
            if not args.no_inject:
                try:
                    run_faultctl(inc.get("reset", ["reset"]))
                except Exception as e:
                    row["reset_error"] = str(e)[:200]
                    row["outcome"] = "FAIL_RESET_ERROR"
        rows.append(row)
        print(f"{row['id']:18s} {row['outcome']:10s} predicted={row.get('predicted_service')}/"
              f"{row.get('predicted_category')} conf={row.get('confidence')} calls={row.get('tool_calls')}")

    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(rows, indent=2, default=str))
    passed = sum(r["outcome"] == "PASS" for r in rows)
    print(f"\n{passed}/{len(rows)} passed. Results and transcripts in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
