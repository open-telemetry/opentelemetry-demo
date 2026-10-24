"""Run the agent on recorded scenarios and score it against eval/expected.yaml.

    python -m eval.run_eval [--scenarios baseline,scenario-06] [--live] [--pause 20]

Default is offline replay of oncall/tests/fixtures/<scenario>/. Scenarios run
one at a time with a pause between them (the Groq free tier rate-limits).
Writes eval/results/<scenario>.json per run and eval/results/summary.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
EXPECTED = HERE / "expected.yaml"
RESULTS = HERE / "results"
FIXTURES = HERE.parent / "oncall" / "tests" / "fixtures"
ALERT = "users report errors when shopping"
BUCKETS = ((0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01))

sys.path.insert(0, str(HERE.parent))


def load_expected(path: Path = EXPECTED) -> dict[str, dict]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {})["scenarios"]


def score(expected: dict, d: dict, report_valid: bool) -> tuple[float, str]:
    """(score, verdict). RED verdicts are the ones a judge penalises hardest."""
    if not report_valid:
        return 0.0, "RED invalid report"
    decision, category, component = d["decision"], d["category"], d["component"]
    if expected["category"] == "no_incident":
        if category == "no_incident" and decision == "no_action":
            return 1.0, "correct"
        if decision == "act":
            return 0.0, "RED confident act on a healthy system"
        return 0.5, "escalated on a healthy system"
    components = {expected["component"], *expected.get("accept_components", [])}
    categories = {expected["category"], *expected.get("accept_categories", [])}
    if decision == "no_action":
        return 0.0, "RED missed incident (no_action)"
    if component in components and category in categories:
        return 1.0, "correct"
    if component in components:
        return 0.5, "partial (category wrong)"
    named = {*d["affected_services"], *(a["hypothesis"] for a in d["alternatives"])}
    if decision == "escalate" and any(c in text for c in components for text in named):
        return 0.5, "escalated, right component named"
    if decision == "act":
        return 0.0, "RED confident act, wrong component"
    return 0.0, "wrong"


def run_scenario(scenario: str, live: bool) -> dict:
    if not live:
        os.environ["TELEMETRY_BACKEND"] = "offline"
        os.environ["OFFLINE_SCENARIO"] = scenario
    from oncall.agent.loop import investigate_and_diagnose
    from oncall.agent.runlog import RunLog
    from oncall.main import _manual_alert
    from oncall.report.output import finalise_report, validate, write

    runlog = RunLog(runs_dir=str(RESULTS / "runs"))
    alert = _manual_alert(None, ALERT)
    started = time.time()
    result = investigate_and_diagnose(alert, runlog=runlog)
    seconds = time.time() - started
    report, notes = finalise_report(alert, result["diagnosis"], runlog)
    valid = not validate(report)
    if valid:
        write(report, RESULTS / "reports")
    usage = runlog.token_usage()
    return {
        "scenario": scenario,
        "run_id": result["run_id"],
        "diagnosis": result["diagnosis"],
        "steps": result["steps"],
        "stopped": result["stopped"],
        "tokens": usage.get("total_tokens", 0),
        "seconds": round(seconds, 1),
        "report_valid": valid,
        "llm_models": report.get("llm_models", []),
        "report_notes": notes,
    }


def calibration(rows: list[dict]) -> list[str]:
    lines = ["| confidence | runs | mean score |", "|---|---|---|"]
    for low, high in BUCKETS:
        inside = [r for r in rows if low <= r["diagnosis"]["confidence"] < high]
        mean = sum(r["score"] for r in inside) / len(inside) if inside else 0.0
        label = f"{low:.1f}-{min(high, 1.0):.1f}"
        lines.append(
            f"| {label} | {len(inside)} | {mean:.2f} |"
            if inside
            else f"| {label} | 0 | - |"
        )
    return lines


def summary(rows: list[dict], expected: dict, live: bool) -> str:
    lines = [
        f"# Eval summary ({'live' if live else 'offline'})",
        "",
        "| scenario | expected | got | confidence | decision | score | verdict | steps | tokens | seconds | LLM |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        e, d = expected[r["scenario"]], r["diagnosis"]
        lines.append(
            f"| {r['scenario']} | {e.get('component')} / {e['category']} "
            f"| {d['component']} / {d['category']} | {d['confidence']:.2f} "
            f"| {d['decision']} | {r['score']} | {r['verdict']} | {r['steps']} "
            f"| {r['tokens']} | {r['seconds']} | {', '.join(r.get('llm_models') or []) or '-'} |"
        )
    total = sum(r["score"] for r in rows)
    red = sum(r["verdict"].startswith("RED") for r in rows)
    lines += [
        "",
        f"**Total {total:.1f} / {len(rows)}**, RED: {red}",
        "",
        "## Calibration",
        *calibration(rows),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.run_eval")
    parser.add_argument(
        "--scenarios", default=None, help="comma-separated; default all"
    )
    parser.add_argument("--live", action="store_true", help="query the running demo")
    parser.add_argument(
        "--pause", type=float, default=20.0, help="seconds between runs"
    )
    parser.add_argument(
        "--fail-on-red",
        action="store_true",
        help="exit non-zero if any scenario gets a RED verdict (CI gate)",
    )
    args = parser.parse_args(argv)

    expected = load_expected()
    names = (
        args.scenarios.split(",")
        if args.scenarios
        else [n for n in expected if args.live or (FIXTURES / n).is_dir()]
    )
    unknown = [n for n in names if n not in expected]
    if unknown:
        parser.error(f"no expected answer for {unknown}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, name in enumerate(names):
        if i:
            time.sleep(args.pause)
        row = run_scenario(name, args.live)
        row["score"], row["verdict"] = score(
            expected[name], row["diagnosis"], row["report_valid"]
        )
        (RESULTS / f"{name}.json").write_text(
            json.dumps(row, indent=2), encoding="utf-8"
        )
        print(
            f"{name}: {row['diagnosis']['component']} / {row['diagnosis']['category']} "
            f"{row['diagnosis']['decision']} {row['diagnosis']['confidence']:.2f} -> "
            f"{row['score']} {row['verdict']} ({row['seconds']} s)",
            flush=True,
        )
        rows.append(row)
    text = summary(rows, expected, args.live)
    (RESULTS / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    red = sum(r["verdict"].startswith("RED") for r in rows)
    if args.fail_on_red and red:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
