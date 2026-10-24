"""Turn a candidate diagnosis plus its evidence ledger into the final report.

    python -m oncall.report <run_dir>

loads ledger.json, candidate.json and run_info.json from a run folder (reports/runs/<run id>/) and writes
report.json and report.md into the same folder. `finalize` does the same from objects already in memory.
Field names come from oncall/schema.py. An escalated report keeps everything the agent found; it only
changes the status and states why a human should look.

Bad input never crashes a run and never leaves a half-written folder: a missing file, a value of the wrong
shape or an unexpected error produces an escalated report that says so, and the two output files are only
written once the report has been built and rendered.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from oncall import schema as S
from oncall.confidence import assess, kind_mismatch
from oncall.validator import load_ledger, validate_evidence

RUN_INFO_MISSING = "run info missing"


def _alternatives(raw) -> list[dict]:
    """alternatives_considered as a list of {hypothesis, why_rejected}; bare strings are accepted."""
    if isinstance(raw, (str, dict)):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out = []
    for entry in raw:
        if isinstance(entry, dict):
            out.append(entry)
        elif isinstance(entry, str) and entry.strip():
            out.append({S.ALT_HYPOTHESIS: entry, S.ALT_WHY_REJECTED: ""})
    return out


def _list(raw) -> list:
    if isinstance(raw, str):
        raw = [raw]
    return raw if isinstance(raw, list) else []


def _ledger_source(ledger):
    """A ledger of an unusable type (null JSON, a number, ...) counts as an empty one."""
    if isinstance(ledger, (list, dict)) or (hasattr(ledger, "list") and callable(ledger.list)):
        return ledger
    return []


def build_report(candidate: dict, ledger, run_info: dict | None, problems: list[str] | None = None,
                 fallback_id: str | None = None) -> dict:
    """`problems` are extra reasons (missing files, ...) that force escalation."""
    candidate = dict(candidate) if isinstance(candidate, dict) else {}
    run_info = run_info if isinstance(run_info, dict) else {}
    candidate[S.ALTERNATIVES] = _alternatives(candidate.get(S.ALTERNATIVES))
    problems = list(problems or [])
    if not run_info and not any(p.startswith(RUN_INFO_MISSING) for p in problems):
        problems.append(RUN_INFO_MISSING)
    validation = validate_evidence(candidate, _ledger_source(ledger))
    assessment = assess(candidate, validation.items, run_info)
    for item in validation.validated:
        mismatch = kind_mismatch(item)
        if mismatch:
            item[S.EV_NOTE] += f"; {mismatch}"
    escalation = problems + assessment.escalation_reasons
    escalated = bool(escalation)
    report = {
        S.INCIDENT_ID: run_info.get(S.RUN_INCIDENT_ID) or fallback_id,
        S.STARTED_AT: run_info.get(S.RUN_STARTED_AT),
        S.TRIGGER: run_info.get(S.RUN_TRIGGER),
        S.STATUS: S.STATUS_ESCALATED if escalated else S.STATUS_DIAGNOSED,
        S.COMPONENT: candidate.get(S.COMPONENT),
        S.CAUSE: candidate.get(S.CAUSE),
        S.CONFIDENCE: assessment.confidence,
        S.STATED_CONFIDENCE: candidate.get(S.STATED_CONFIDENCE),
        S.CONFIDENCE_REASONS: assessment.reasons,
        S.EVIDENCE: validation.items,
        S.ALTERNATIVES: candidate[S.ALTERNATIVES],
        S.STEPS: _list(candidate.get(S.STEPS)),
        S.LIMITATIONS: _list(candidate.get(S.LIMITATIONS)),
        S.ESCALATION_REASON: "; ".join(escalation) if escalated else None,
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


def _error_report(reason: str, run_info: dict, fallback_id: str | None, problems: list[str]) -> dict:
    """The escalated report used when building the real one failed unexpectedly."""
    report = {name: None for name in S.REPORT_FIELDS}
    report.update({
        S.INCIDENT_ID: run_info.get(S.RUN_INCIDENT_ID) or fallback_id,
        S.STARTED_AT: run_info.get(S.RUN_STARTED_AT), S.TRIGGER: run_info.get(S.RUN_TRIGGER),
        S.STATUS: S.STATUS_ESCALATED, S.COMPONENT: S.UNKNOWN_COMPONENT,
        S.CAUSE: "No diagnosis could be reported.", S.CONFIDENCE: 0.0, S.STATED_CONFIDENCE: None,
        S.CONFIDENCE_REASONS: [], S.EVIDENCE: [], S.ALTERNATIVES: [], S.STEPS: [],
        S.LIMITATIONS: [reason], S.ESCALATION_REASON: "; ".join(problems + [reason]), S.WARNINGS: [],
    })
    return report


def _write_atomically(out_dir: Path, files: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    temps = {}
    try:
        for name, text in files.items():
            temp = out_dir / f".{name}.tmp"
            temp.write_text(text, encoding="utf-8")
            temps[name] = temp
        for name, temp in temps.items():
            os.replace(temp, out_dir / name)
    finally:
        for temp in temps.values():
            temp.unlink(missing_ok=True)


def finalize(candidate: dict, ledger, run_info: dict | None, out_dir, problems: list[str] | None = None,
             fallback_id: str | None = None) -> dict:
    """Validate the candidate against the ledger, compute confidence, write report.json and report.md
    into out_dir, and return the report. Anything unexpected in the inputs gives an escalated report."""
    info = run_info if isinstance(run_info, dict) else {}
    try:
        report = build_report(candidate, ledger, run_info, problems, fallback_id)
        markdown = render_markdown(report)
        text = json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n"
    except Exception as exc:
        report = _error_report(f"the report could not be built from the run data ({type(exc).__name__}: {exc})",
                               info, fallback_id, list(problems or []))
        markdown = render_markdown(report)
        text = json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n"
    _write_atomically(Path(out_dir), {S.REPORT_JSON_FILE: text, S.REPORT_MD_FILE: markdown})
    return report


def _read_json(path: Path, problems: list[str], missing_text: str):
    """The parsed file, or None (with a problem noted) when it does not exist. Invalid JSON raises ValueError."""
    if not path.is_file():
        problems.append(missing_text)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def finalize_run_dir(run_dir) -> dict:
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"{run_dir} is not a run folder")
    problems: list[str] = []
    candidate = _read_json(run_dir / S.CANDIDATE_FILE, problems, f"{S.CANDIDATE_FILE} is missing")
    run_info = _read_json(run_dir / S.RUN_INFO_FILE, problems, f"{RUN_INFO_MISSING} ({S.RUN_INFO_FILE} not found)")
    ledger = _read_json(run_dir / S.LEDGER_FILE, problems, f"{S.LEDGER_FILE} is missing")
    ledger = ledger if isinstance(ledger, list) else []
    return finalize(candidate, ledger, run_info, run_dir, problems, fallback_id=run_dir.name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a saved run and write report.json and report.md into it")
    parser.add_argument("run_dir", help="a run folder, e.g. reports/runs/inc-20261024-101500-ab12")
    args = parser.parse_args(argv)
    try:
        report = finalize_run_dir(args.run_dir)
    except (OSError, ValueError) as exc:  # no such folder, unreadable file or invalid JSON
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
