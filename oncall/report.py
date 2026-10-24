"""Turn a candidate diagnosis plus its evidence ledger into the final report.

    python -m oncall.report <run_dir>

loads ledger.json, candidate.json and run_info.json from a run folder (reports/runs/<run id>/) and writes
report.json and report.md into the same folder. `finalize` does the same from objects already in memory.
Field names come from oncall/schema.py. An escalated report keeps everything the agent found; it only
changes the status and states why a human should look.
"""
import argparse
import json
import sys
from pathlib import Path

from oncall import schema as S
from oncall.confidence import assess
from oncall.validator import load_ledger, validate_evidence


def build_report(candidate: dict, ledger, run_info: dict | None) -> dict:
    run_info = run_info or {}
    validation = validate_evidence(candidate, ledger)
    assessment = assess(candidate, validation.items, run_info)
    escalated = assessment.escalate
    report = {
        S.INCIDENT_ID: run_info.get(S.RUN_INCIDENT_ID),
        S.STARTED_AT: run_info.get(S.RUN_STARTED_AT),
        S.TRIGGER: run_info.get(S.RUN_TRIGGER),
        S.STATUS: S.STATUS_ESCALATED if escalated else S.STATUS_DIAGNOSED,
        S.COMPONENT: candidate.get(S.COMPONENT),
        S.CAUSE: candidate.get(S.CAUSE),
        S.CONFIDENCE: assessment.confidence,
        S.STATED_CONFIDENCE: candidate.get(S.STATED_CONFIDENCE),
        S.CONFIDENCE_REASONS: assessment.reasons,
        S.EVIDENCE: validation.items,
        S.ALTERNATIVES: candidate.get(S.ALTERNATIVES) or [],
        S.STEPS: candidate.get(S.STEPS) or [],
        S.LIMITATIONS: candidate.get(S.LIMITATIONS) or [],
        S.ESCALATION_REASON: "; ".join(assessment.escalation_reasons) if escalated else None,
        S.WARNINGS: validation.warnings,
    }
    return {name: report[name] for name in S.REPORT_FIELDS}


def render_markdown(report: dict) -> str:
    escalated = report[S.STATUS] == S.STATUS_ESCALATED
    lines = [f"# Incident {report[S.INCIDENT_ID] or '(no id)'}: "
             f"{'ESCALATED to a human' if escalated else 'diagnosed'}", ""]
    if report[S.TRIGGER]:
        lines += [f"Symptom given: {report[S.TRIGGER]}", ""]
    if report[S.STARTED_AT]:
        lines += [f"Started: {report[S.STARTED_AT]}", ""]

    lines += ["## What is broken", "",
              f"- Component: **{report[S.COMPONENT]}**" + (" (agent's best finding, not asserted)" if escalated else ""),
              f"- Cause: {report[S.CAUSE]}", ""]
    if escalated:
        lines += [f"Why a human should look: {report[S.ESCALATION_REASON]}", ""]

    lines += ["## Evidence", ""]
    if not report[S.EVIDENCE]:
        lines.append("- none cited")
    for item in report[S.EVIDENCE]:
        mark = "✓" if item[S.EV_VALIDATED] else "✗"
        value = f" ({item[S.EV_VALUE]})" if item.get(S.EV_VALUE) else ""
        lines.append(f"- {mark} [{item[S.EV_LEDGER_ID]}] {item[S.EV_KIND]}: {item[S.EV_CLAIM]}")
        lines.append(f"  - quote: `{item[S.EV_QUOTE]}`{value}")
        lines.append(f"  - check: {item[S.EV_NOTE]}")
    lines.append("")

    stated, final = report[S.STATED_CONFIDENCE], report[S.CONFIDENCE]
    lines += ["## Confidence", "", f"- Final: {final:.2f} (the agent stated {stated})"]
    lines += [f"- {reason}" for reason in report[S.CONFIDENCE_REASONS]] or ["- no cap lowered it"]
    lines.append("")

    if report[S.ALTERNATIVES]:
        lines += ["## Alternatives ruled out", ""]
        lines += [f"- {a.get(S.ALT_HYPOTHESIS)}: {a.get(S.ALT_WHY_REJECTED)}" for a in report[S.ALTERNATIVES]]
        lines.append("")

    unchecked = list(report[S.LIMITATIONS]) + list(report[S.WARNINGS])
    lines += ["## What was not checked", ""]
    lines += [f"- {note}" for note in unchecked] or ["- nothing was recorded"]
    lines.append("")
    return "\n".join(lines)


def finalize(candidate: dict, ledger, run_info: dict | None, out_dir) -> dict:
    """Validate the candidate against the ledger, compute confidence, write report.json and report.md
    into out_dir, and return the report."""
    report = build_report(candidate, ledger, run_info)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / S.REPORT_JSON_FILE).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    (out_dir / S.REPORT_MD_FILE).write_text(render_markdown(report), encoding="utf-8")
    return report


def finalize_run_dir(run_dir) -> dict:
    run_dir = Path(run_dir)
    candidate = json.loads((run_dir / S.CANDIDATE_FILE).read_text(encoding="utf-8"))
    run_info = json.loads((run_dir / S.RUN_INFO_FILE).read_text(encoding="utf-8"))
    ledger = load_ledger(run_dir / S.LEDGER_FILE)
    return finalize(candidate, ledger, run_info, run_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a saved run and write report.json and report.md into it")
    parser.add_argument("run_dir", help="a run folder, e.g. reports/runs/inc-20261024-101500-ab12")
    args = parser.parse_args(argv)
    try:
        report = finalize_run_dir(args.run_dir)
    except (OSError, ValueError) as exc:  # missing file or invalid JSON
        print(f"cannot build a report from {args.run_dir}: {exc}", file=sys.stderr)
        return 2
    print(f"{report[S.STATUS].upper()}  component: {report[S.COMPONENT]}  confidence: {report[S.CONFIDENCE]:.2f} "
          f"(stated {report[S.STATED_CONFIDENCE]})")
    if report[S.ESCALATION_REASON]:
        print(f"escalation reason: {report[S.ESCALATION_REASON]}")
    print(f"wrote {Path(args.run_dir) / S.REPORT_JSON_FILE} and {Path(args.run_dir) / S.REPORT_MD_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
