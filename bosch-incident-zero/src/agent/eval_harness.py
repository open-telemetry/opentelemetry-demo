"""Run approved practice incidents through the agent and score them.

    FAULTCTL_CMD="<organisers' faultctl>" python -m src.agent.eval_harness cases.json [--only ID ...]
    python -m src.agent.eval_harness cases.json --no-inject --only ID   # incident already active

cases.json is a list of approved cases. Expected answers are read only by this evaluator;
the agent receives nothing but the alert text:
    [{"id": "practice-01",
      "official": true,                              # mentor-selected official practice incident
      "source": "mentor list, 2026-10-24",           # who approved it
      "inject": ["inject", "<incident name>"],       # appended to FAULTCTL_CMD
      "reset": ["reset"],
      "alert": "Error rate above 5% on checkout",    # the only text the agent sees
      "warmup_seconds": 90,
      "expected": {"service": "payment", "category": "dependency_unreachable"}}]

Injection and reset go only through the organisers' faultctl. The harness never touches flagd.
Outputs in <REPORT_OUTPUT_DIR>/eval-<stamp>/: one folder per case (transcript.json, report.json),
results.jsonl (one row appended as each case finishes, so an interrupted run keeps its rows),
results.json (all rows) and summary.json (counts per outcome).

Outcomes, checked in this order:
    ERROR_INFRA             faultctl failed, the run crashed, or every tool call hit an unavailable source
    ERROR_MODEL             the LLM failed (quota, network, config) or produced no parseable diagnosis
    ESCALATED               the agent escalated to a human (low confidence); never counted as a pass
    NO_DIAGNOSIS            not escalated, but no root-cause service was named
    FAIL                    wrong root-cause service or category
    ERROR_SCHEMA            right diagnosis, but the report failed schema validation
    FAIL_INVALID_CITATIONS  right diagnosis, but some cited evidence failed validation
    PASS                    right service (and category, when expected), valid report and citations

A missing cases file or FAULTCTL_CMD stops the run with a BLOCKED message (exit 2): both come
from the organisers and are never substituted.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .guards import CATEGORIES

OUTCOMES = ("PASS", "FAIL", "ESCALATED", "NO_DIAGNOSIS", "FAIL_INVALID_CITATIONS", "ERROR_SCHEMA",
            "ERROR_MODEL", "ERROR_INFRA")
_CASE_KEYS = {"id", "official", "source", "inject", "reset", "alert", "warmup_seconds", "expected", "notes"}
_EXPECTED_KEYS = {"service", "category"}
# Case ids become directory names: letters, digits, dot, underscore and hyphen only.
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# faultctl sub-commands, which are not incident names and may appear in ordinary alert wording.
_FAULTCTL_VERBS = {"inject", "reset", "enable", "disable", "on", "off", "start", "stop"}
# Summaries of tool results caused by the model's own call (bad tool name or arguments), not by telemetry.
_MODEL_CALL_ERRORS = ("Unknown tool", "Invalid arguments", "Arguments were not valid JSON")


def _words(text: str) -> str:
    """Lowercase, split camelCase, and treat '-', '_' and whitespace as one separator."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return " ".join(re.split(r"[-_\s]+", spaced.lower())).strip()


def _leaks(name: str, alert: str) -> bool:
    """True when the alert names ``name`` in any spelling (payment-failure, paymentFailure, ...)."""
    n, a = _words(name), _words(alert)
    if not n:
        return False
    if len(n.replace(" ", "")) <= 3:
        return re.search(rf"\b{re.escape(n)}\b", a) is not None
    return n in a or n.replace(" ", "") in a.replace(" ", "")


class CaseError(ValueError):
    """The cases file is not usable; the message lists every problem found."""


class FaultctlError(RuntimeError):
    pass


@dataclass
class Case:
    id: str
    alert: str
    expected: Dict[str, Any]
    official: bool = False
    source: str = ""
    inject: List[str] = field(default_factory=list)
    reset: List[str] = field(default_factory=lambda: ["reset"])
    warmup_seconds: int = 90


def parse_cases(raw: Any, require_inject: bool = False) -> List[Case]:
    """Validate the cases file. ``require_inject`` is set when faultctl will inject each case."""
    if not isinstance(raw, list) or not raw:
        raise CaseError("cases file must hold a non-empty JSON list")
    problems: List[str] = []
    cases: List[Case] = []
    seen = set()
    for i, c in enumerate(raw):
        where = f"case {i}" + (f" ({c.get('id')})" if isinstance(c, dict) and c.get("id") else "")
        if not isinstance(c, dict):
            problems.append(f"{where}: not an object")
            continue
        extra = set(c) - _CASE_KEYS
        if extra:
            problems.append(f"{where}: unknown keys {sorted(extra)}")
        cid, alert, expected = c.get("id"), c.get("alert"), c.get("expected")
        if not isinstance(cid, str) or not cid.strip():
            problems.append(f"{where}: 'id' is required")
        elif not _ID_RE.match(cid):
            problems.append(f"{where}: 'id' may only use letters, digits, '.', '_' and '-'")
        elif cid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(cid)
        if not isinstance(alert, str) or not alert.strip():
            problems.append(f"{where}: 'alert' is required and must be a string")
            alert = ""
        if not isinstance(expected, dict) or not isinstance(expected.get("service"), str) \
                or not expected["service"].strip():
            problems.append(f"{where}: 'expected.service' is required and must be a string")
            continue
        unknown = set(expected) - _EXPECTED_KEYS
        if unknown:
            problems.append(f"{where}: unknown expected keys {sorted(unknown)}")
        category = expected.get("category")
        if category is not None and (not isinstance(category, str) or category not in CATEGORIES):
            problems.append(f"{where}: expected.category {category!r} is not one of {CATEGORIES}")
            category = None
        official = c.get("official", False)
        if not isinstance(official, bool):
            problems.append(f"{where}: 'official' must be true or false")
        source = c.get("source", "")
        if not isinstance(source, str):
            problems.append(f"{where}: 'source' must be a string")
        warmup = c.get("warmup_seconds", 90)
        if isinstance(warmup, bool) or not isinstance(warmup, int) or warmup < 0:
            problems.append(f"{where}: 'warmup_seconds' must be a non-negative integer")
            warmup = 0
        inject, reset = c.get("inject", []), c.get("reset", ["reset"])
        for key, value in (("inject", inject), ("reset", reset)):
            if not isinstance(value, list) or not all(isinstance(a, str) and a for a in value):
                problems.append(f"{where}: '{key}' must be a list of non-empty strings")
        if not isinstance(inject, list) or not all(isinstance(a, str) for a in inject):
            inject = []
        if not isinstance(reset, list) or not reset:
            if isinstance(reset, list):
                problems.append(f"{where}: 'reset' must not be empty")
            reset = ["reset"]
        if require_inject and not inject:
            problems.append(f"{where}: 'inject' is required when faultctl injects the fault")
        # The alert is the agent's only input: it must not leak the fault name or the expected category.
        leaks = [a for a in inject if a.lower() not in _FAULTCTL_VERBS and not a.startswith("-")
                 and _leaks(a, alert)]
        if category and _leaks(category, alert):
            leaks.append(category)
        if leaks:
            problems.append(f"{where}: alert text reveals {leaks}")
        cases.append(Case(
            id=str(cid), alert=str(alert), expected=dict(expected), official=official is True,
            source=str(source), inject=list(inject), reset=list(reset), warmup_seconds=warmup,
        ))
    if problems:
        raise CaseError("; ".join(problems))
    return cases


def faultctl_runner(base_cmd: str, timeout: int = 300) -> Callable[[List[str]], str]:
    def run(args: List[str]) -> str:
        try:
            proc = subprocess.run([*shlex.split(base_cmd), *args], capture_output=True, text=True,
                                  timeout=timeout)
        except (OSError, subprocess.SubprocessError) as e:
            raise FaultctlError(f"faultctl {' '.join(args)}: {type(e).__name__}: {e}") from e
        if proc.returncode != 0:
            raise FaultctlError(f"faultctl {' '.join(args)} exited {proc.returncode}: {proc.stderr.strip()[:300]}")
        return proc.stdout.strip()
    return run


class CountingFactory:
    """Wraps a session factory and counts model requests (send calls) per case."""

    def __init__(self, inner: Callable[[str, Sequence[Dict[str, Any]]], Any]) -> None:
        self.inner = inner
        self.requests = 0

    def __call__(self, system: str, tools: Sequence[Dict[str, Any]]) -> Any:
        session = self.inner(system, tools)
        factory = self

        class _Counted:
            def send(self, *args: Any, **kwargs: Any) -> Any:
                factory.requests += 1
                return session.send(*args, **kwargs)

        return _Counted()


def score(expected: Dict[str, Any], transcript: Any) -> Dict[str, Any]:
    """Score one transcript against the evaluator-only expected answer."""
    diag = transcript.diagnosis or {}
    root = diag.get("root_cause") or {}
    gate = transcript.gate or {}
    observed = {
        "service": root.get("service") or None,
        "category": root.get("category") or None,
        "impacted_services": diag.get("impacted_services") or [],
        "confidence": gate.get("final_confidence"),
        "escalated": bool(gate.get("escalate", True)),
    }
    has_diagnosis = bool(observed["service"])
    service_match = has_diagnosis and observed["service"] == expected.get("service")
    category_match = has_diagnosis and (expected.get("category") is None
                                        or observed["category"] == expected.get("category"))
    invalid_citations = gate.get("invalid_citations") or 0
    schema_valid = bool(transcript.report_schema_valid)
    errors = list(transcript.errors or [])
    statuses = [c.get("result", {}).get("status") for c in transcript.tool_calls]

    model_calls = [str(c.get("result", {}).get("summary", "")).startswith(_MODEL_CALL_ERRORS)
                   for c in transcript.tool_calls]
    if statuses and all(s in ("source_unavailable", "error") for s in statuses) and not all(model_calls):
        outcome, detail = "ERROR_INFRA", "every tool call returned source_unavailable or error"
    elif statuses and all(model_calls):
        outcome, detail = "ERROR_MODEL", "every tool call named an unknown tool or had invalid arguments"
    elif any(e.startswith("LLM failure") for e in errors) or any("no parseable diagnosis" in e for e in errors):
        outcome, detail = "ERROR_MODEL", "; ".join(errors)[:400]
    elif observed["escalated"]:
        outcome, detail = "ESCALATED", "; ".join(gate.get("reasons") or [])[:400] or "agent escalated"
    elif not has_diagnosis:
        outcome, detail = "NO_DIAGNOSIS", "the diagnosis names no root-cause service"
    elif not (service_match and category_match):
        outcome = "FAIL"
        detail = (f"expected {expected.get('service')}/{expected.get('category')}, "
                  f"observed {observed['service']}/{observed['category']}")
    elif not schema_valid:
        outcome, detail = "ERROR_SCHEMA", "; ".join(transcript.report_schema_errors or [])[:400]
    elif invalid_citations:
        outcome, detail = "FAIL_INVALID_CITATIONS", f"{invalid_citations} citation(s) failed validation"
    else:
        outcome, detail = "PASS", ""
    return {
        "outcome": outcome,
        "detail": detail,
        "expected": dict(expected),
        "observed": observed,
        "checks": {
            "diagnosis_correct": service_match and category_match,
            "service_match": service_match,
            "category_match": category_match,
            "schema_valid": schema_valid,
            "schema_errors": list(transcript.report_schema_errors or []),
            "citations_valid": not invalid_citations,
        },
        "tool_calls": len(transcript.tool_calls),
        "step_cap_hit": bool(getattr(transcript, "step_cap_hit", False)),
        "invalid_citations": invalid_citations,
        "errors": errors,
    }


def run_cases(
    cases: Sequence[Case],
    run_agent: Callable[[str, str], Any],
    counter: CountingFactory,
    faultctl: Optional[Callable[[List[str]], str]],
    stamp: str,
    out_dir: Path,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> List[Dict[str, Any]]:
    """Run each case. ``run_agent(alert, incident_id)`` is the only door to the agent."""
    rows: List[Dict[str, Any]] = []
    for case in cases:
        incident_id = f"{case.id}-{stamp}"
        row: Dict[str, Any] = {"id": case.id, "official": case.official, "source": case.source,
                               "incident_id": incident_id, "expected": dict(case.expected)}
        counter.requests = 0
        started = time.monotonic()
        try:
            if faultctl is not None:
                faultctl(case.reset)
                faultctl(case.inject)
                sleep(case.warmup_seconds)
            transcript = run_agent(case.alert, incident_id)
            row.update(score(case.expected, transcript))
            row["transcript_path"] = str(out_dir / incident_id / "transcript.json")
            row["report_path"] = str(out_dir / incident_id / "report.json")
        except FaultctlError as e:
            row.update(outcome="ERROR_INFRA", detail=str(e)[:400])
        except Exception as e:  # a crash is recorded, never scored as a diagnosis
            row.update(outcome="ERROR_INFRA", detail=f"{type(e).__name__}: {str(e)[:300]}")
        finally:
            if faultctl is not None:
                try:
                    faultctl(case.reset)
                except Exception as e:
                    row["reset_error"] = str(e)[:300]
                    log(f"WARNING: reset after {case.id} FAILED, the demo may still have the fault active: "
                        f"{row['reset_error']}")
        row["llm_requests"] = counter.requests
        row["duration_seconds"] = round(time.monotonic() - started, 1)
        rows.append(row)
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "results.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
        obs = row.get("observed") or {}
        log(f"{case.id:18s} {row['outcome']:12s} observed={obs.get('service')}/{obs.get('category')} "
            f"conf={obs.get('confidence')} calls={row.get('tool_calls')} llm_requests={row['llm_requests']}")
    return rows


def summarize(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {o: sum(r["outcome"] == o for r in rows) for o in OUTCOMES}
    official = [r for r in rows if r.get("official")]
    return {
        "cases": len(rows),
        "outcomes": counts,
        "official_cases": len(official),
        "official_passed": sum(r["outcome"] == "PASS" for r in official),
        "llm_requests_total": sum(r.get("llm_requests", 0) for r in rows),
        "reset_errors": sum(bool(r.get("reset_error")) for r in rows),
        "note": "Only official cases run with the organisers' faultctl count toward the checkpoint.",
    }


def write_outputs(out_dir: Path, rows: Sequence[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {**meta, **summarize(rows)}
    (out_dir / "results.json").write_text(json.dumps(list(rows), indent=2, default=str))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.agent.eval_harness")
    p.add_argument("cases", type=Path, help="JSON list of approved cases (evaluator-only)")
    p.add_argument("--only", nargs="*", help="Run only these case ids")
    p.add_argument("--no-inject", action="store_true",
                   help="Do not call faultctl; the single selected incident is already active.")
    args = p.parse_args(argv)

    if not args.cases.is_file():
        print(f"BLOCKED: cases file '{args.cases}' not found. Get the approved practice incidents "
              "from the organisers.", file=sys.stderr)
        return 2
    try:
        cases = parse_cases(json.loads(args.cases.read_text(encoding="utf-8")),
                            require_inject=not args.no_inject)
    except (OSError, ValueError) as e:
        print(f"eval_harness: {e}", file=sys.stderr)
        return 2
    if args.only:
        missing = set(args.only) - {c.id for c in cases}
        if missing:
            print(f"eval_harness: unknown case ids {sorted(missing)}", file=sys.stderr)
            return 2
        cases = [c for c in cases if c.id in args.only]
    faultctl = None
    if args.no_inject:
        if len(cases) != 1:
            print("eval_harness: --no-inject needs exactly one case (the incident that is already active)",
                  file=sys.stderr)
            return 2
    else:
        base = os.environ.get("FAULTCTL_CMD", "").strip()
        if not base:
            print("BLOCKED: FAULTCTL_CMD is not set; point it at the organisers' faultctl "
                  "or use --no-inject for an incident that is already active.", file=sys.stderr)
            return 2
        faultctl = faultctl_runner(base)

    from ..config import Settings
    from .agent import IncidentAgent
    from .llm import LLMConfig, LLMConfigError, session_factory
    from .tools import ToolBox, ToolContext

    settings = Settings()
    try:
        cfg = LLMConfig.from_env()
        counter = CountingFactory(session_factory(cfg))
    except LLMConfigError as e:
        print(f"eval_harness: {e}", file=sys.stderr)
        return 2
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = Path(settings.report_output_dir)
    out = (out if out.is_absolute() else settings.root_dir / out) / f"eval-{stamp}"
    agent = IncidentAgent(ToolBox(ToolContext(settings)), counter, output_dir=out)

    rows = run_cases(cases, lambda alert, incident_id: agent.run(alert, incident_id=incident_id),
                     counter, faultctl, stamp, out)
    summary = write_outputs(out, rows, {
        "started_stamp": stamp, "provider": cfg.provider, "model": cfg.model,
        "injection": "none (--no-inject)" if args.no_inject else "FAULTCTL_CMD",
    })
    print(f"\n{summary['outcomes']['PASS']}/{summary['cases']} passed "
          f"({summary['official_passed']}/{summary['official_cases']} official). "
          f"LLM requests: {summary['llm_requests_total']}. Results in {out}")
    if summary["reset_errors"]:
        print(f"WARNING: {summary['reset_errors']} reset(s) failed; reset the demo with faultctl before "
              "trusting it again.", file=sys.stderr)
        return 1
    return 0 if summary["outcomes"]["PASS"] == summary["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
