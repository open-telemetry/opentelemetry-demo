"""Calibration: how often each confidence level was right, from evaluation harness results.

Usage:
    python scripts/calibration_report.py                          # every eval-*/results.json under incident_output
    python scripts/calibration_report.py incident_output/eval-20261024-050000 other/results.json
    python scripts/calibration_report.py --json

This is an evaluator tool: it reads results.json rows, which hold the expected answers, so it must never be
called from the agent. A directory falls back to results.jsonl when its run was interrupted before
results.json was written. Rows whose outcome is ERROR_INFRA or ERROR_MODEL produced no usable diagnosis and
are counted apart, not as wrong answers.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("high", "medium", "low")
_NOT_SCORED = ("ERROR_INFRA", "ERROR_MODEL")


def _result_files(paths: Iterable[Path]) -> List[Path]:
    found: List[Path] = []
    for p in paths:
        if p.is_file():
            found.append(p)
            continue
        dirs = [p] if (p / "results.json").exists() or (p / "results.jsonl").exists() else []
        dirs += sorted(d for d in p.glob("eval-*") if d.is_dir()) if p.is_dir() else []
        for d in dirs:
            if (d / "results.json").exists():
                found.append(d / "results.json")
            elif (d / "results.jsonl").exists():
                found.append(d / "results.jsonl")
    return list(dict.fromkeys(found))


def load_rows(files: Iterable[Path]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
            if f.suffix == ".jsonl":
                rows += [json.loads(line) for line in text.splitlines() if line.strip()]
            else:
                data = json.loads(text)
                rows += data if isinstance(data, list) else []
        except (OSError, ValueError) as e:
            print(f"calibration_report: skipping {f}: {e}", file=sys.stderr)
    return [r for r in rows if isinstance(r, dict)]


def _correct(row: Dict[str, Any]) -> bool:
    checks = row.get("checks") or {}
    if "diagnosis_correct" in checks:
        return bool(checks["diagnosis_correct"])
    return bool(checks.get("service_match") and checks.get("category_match"))


def calibrate(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Accuracy per confidence level. Escalated rows are reported with what the diagnosis would have scored."""
    table = {lvl: {"cases": 0, "correct": 0, "escalated": 0, "passed": 0} for lvl in (*LEVELS, "unknown")}
    not_scored = 0
    for r in rows:
        if r.get("outcome") in _NOT_SCORED:
            not_scored += 1
            continue
        lvl = str((r.get("observed") or {}).get("confidence") or "unknown").lower()
        cell = table[lvl if lvl in table else "unknown"]
        cell["cases"] += 1
        cell["correct"] += _correct(r)
        cell["escalated"] += r.get("outcome") == "ESCALATED"
        cell["passed"] += r.get("outcome") == "PASS"
    for cell in table.values():
        cell["accuracy"] = round(cell["correct"] / cell["cases"], 3) if cell["cases"] else None
    scored = sum(c["cases"] for c in table.values())
    ordered = [table[lvl]["accuracy"] for lvl in LEVELS if table[lvl]["accuracy"] is not None]
    return {
        "levels": {k: v for k, v in table.items() if k != "unknown" or v["cases"]},
        "scored_cases": scored,
        "not_scored": not_scored,
        "overall_accuracy": round(sum(c["correct"] for c in table.values()) / scored, 3) if scored else None,
        # Calibrated means higher confidence is never less accurate than lower confidence.
        "monotonic": all(a >= b for a, b in zip(ordered, ordered[1:])) if len(ordered) > 1 else None,
    }


def render(report: Dict[str, Any], files: List[Path]) -> str:
    lines = [f"Calibration over {report['scored_cases']} scored case(s) from {len(files)} file(s)"
             f" ({report['not_scored']} not scored: infra or model errors)", "",
             f"{'confidence':12s} {'cases':>5s} {'correct':>7s} {'accuracy':>8s} {'escalated':>9s} {'PASS':>5s}"]
    for lvl, c in report["levels"].items():
        acc = "-" if c["accuracy"] is None else f"{c['accuracy']:.0%}"
        lines.append(f"{lvl:12s} {c['cases']:5d} {c['correct']:7d} {acc:>8s} {c['escalated']:9d} {c['passed']:5d}")
    overall = report["overall_accuracy"]
    lines += ["", f"overall accuracy: {'-' if overall is None else f'{overall:.0%}'}"]
    if report["monotonic"] is not None:
        lines.append("higher confidence is " + ("never less accurate (calibrated ordering)" if report["monotonic"]
                                                else "LESS accurate than a lower level (miscalibrated)"))
    if report["scored_cases"] < 10:
        lines.append("note: fewer than 10 scored cases; these rates are anecdotes, not measurements")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python scripts/calibration_report.py", description=__doc__.splitlines()[0])
    p.add_argument("paths", nargs="*", type=Path, help="results.json/.jsonl files or eval directories")
    p.add_argument("--json", action="store_true", help="Print the report as JSON.")
    args = p.parse_args(argv)
    files = _result_files(args.paths or [ROOT / "incident_output"])
    if not files:
        print("calibration_report: no results.json found; run the evaluation harness first", file=sys.stderr)
        return 2
    report = calibrate(load_rows(files))
    print(json.dumps(report, indent=2) if args.json else render(report, files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
