"""Follow an agent run live, in a second terminal.

Usage:
    python scripts/watch_run.py                      # new events from now on
    python scripts/watch_run.py --incident DEMO-002  # one incident only
    python scripts/watch_run.py --from-start         # replay the audit log first, then follow
    python scripts/watch_run.py --once               # print what exists and exit

Sources, all read-only:
    audit_logs/audit.jsonl                    one JSON event per line (ts or timestamp, incident_id, event, ...)
    incident_output/<incident>/transcript.json  tool calls, model notes, diagnosis, gate (written when a run ends)
    incident_output/<incident>/run.log        plain-text copy of the same events; read only when there is
                                              no audit log, so nothing is shown twice

A missing file, a half-written last line or a transcript caught mid-write is skipped and retried.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN = (f"\033[{n}m" for n in (31, 32, 33, 34, 35, 36))

# Event name -> (label, colour). Legacy names written by src/approval/pipeline.py are included.
EVENT_STYLES: Dict[str, Tuple[str, str]] = {
    "ALERT_RECEIVED": ("ALERT", BOLD + CYAN),
    "TOOL_CALL": ("TOOL", DIM),
    "MODEL_NOTE": ("NOTE", DIM),
    "DIAGNOSIS": ("DIAGNOSIS", BOLD + MAGENTA),
    "GATE": ("GATE", MAGENTA),
    "PLAN": ("PLAN", CYAN),
    "APPROVAL_REQUESTED": ("APPROVAL?", BOLD + YELLOW),
    "APPROVAL_DECISION": ("APPROVAL", YELLOW),
    "ACTION_EXECUTED": ("ACTION", CYAN),
    "DRY_RUN": ("DRY RUN", CYAN),
    "ACTION_REFUSED": ("REFUSED", RED),
    "ACTION_EXECUTED_DRY_RUN": ("DRY RUN", CYAN),
    "ACTION_REJECTED": ("REJECTED", RED),
    "VERIFICATION": ("VERIFY", GREEN),
    "ROLLBACK": ("ROLLBACK", BOLD + RED),
    "ESCALATION": ("ESCALATION", BOLD + RED),
    "KILL_SWITCH": ("KILL SWITCH", BOLD + RED),
    "ACTION_HALTED_BY_KILL_SWITCH": ("KILL SWITCH", BOLD + RED),
    "REPORT_WRITTEN": ("REPORT", GREEN),
    "UI_EVENT": ("UI", DIM),
    "ERROR": ("ERROR", BOLD + RED),
    "LOG": ("LOG", DIM),
}
STATUS_COLOURS = {"ok": GREEN, "no_data": YELLOW, "source_unavailable": RED, "error": RED}
_ENVELOPE = {"ts", "timestamp", "incident_id", "event", "summary", "data"}


@dataclass
class Event:
    ts: str
    incident_id: str
    event: str
    summary: str
    colour: str = ""


def _short_time(ts: Any) -> str:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    except ValueError:
        return str(ts or "")[:8]


def _compact(values: Dict[str, Any], limit: int = 160) -> str:
    text = " ".join(f"{k}={v}" for k, v in values.items() if v not in (None, "", [], {}))
    return text[:limit]


def _good_or_bad(ok: Optional[bool]) -> str:
    return GREEN if ok else RED if ok is False else YELLOW


def audit_event(raw: Dict[str, Any]) -> Event:
    """Turn one audit.jsonl object into a display event; unknown shapes are shown generically."""
    name = str(raw.get("event") or "EVENT")
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    extra = {k: v for k, v in raw.items() if k not in _ENVELOPE}
    summary = str(raw.get("summary") or "") or _compact({**data, **extra})
    colour = EVENT_STYLES.get(name, ("", ""))[1]
    merged = {**extra, **data}
    review = merged.get("review")
    if name == "GATE" and isinstance(review, dict) and review.get("verdict"):
        if "review=" not in summary:
            summary += f"  review {review['verdict']}"
        before, after = review.get("confidence_before"), review.get("confidence_after")
        if before and after and before != after:
            summary += f" (confidence {before} -> {after})"
    usage = merged.get("token_usage")
    if isinstance(usage, dict) and "tokens" not in summary:
        summary += f"  (tokens in/out {usage.get('prompt_tokens', 0)}/{usage.get('completion_tokens', 0)})"
    if name == "TOOL_CALL" and merged.get("status") in STATUS_COLOURS:
        colour = DIM if merged["status"] == "ok" else STATUS_COLOURS[merged["status"]]
    elif name in ("APPROVAL_DECISION", "VERIFICATION"):
        verdict = str(merged.get("decision") or merged.get("verdict") or merged.get("status") or "").upper()
        ok = merged.get("approved", merged.get("recovered", merged.get("recovery_verified")))
        if verdict in ("APPROVED", "RECOVERED", "VERIFIED", "PASS"):
            ok = True
        elif verdict in ("REJECTED", "DENIED", "TIMEOUT", "NOT_RECOVERED", "FAILED", "FAIL"):
            ok = False
        elif verdict in ("NO_DATA", "NOT_VERIFIED_DRY_RUN"):
            ok = None
        colour = _good_or_bad(ok)
    elif name == "KILL_SWITCH" and merged.get("engaged") is False:
        colour = DIM
    elif name == "GATE":
        colour = YELLOW if merged.get("escalate") else GREEN
    return Event(str(raw.get("ts") or raw.get("timestamp") or ""), str(raw.get("incident_id") or ""),
                 name, summary, colour)


def transcript_events(t: Dict[str, Any], skip: Set[str], printed_calls: Set[int]) -> List[Event]:
    """Events from a saved transcript, leaving out kinds the audit log already streamed."""
    inc, out = str(t.get("incident_id") or ""), []
    if "ALERT_RECEIVED" not in skip and t.get("alert") and -1 not in printed_calls:
        out.append(Event(t.get("started_at", ""), inc, "ALERT_RECEIVED", t["alert"]))
        printed_calls.add(-1)
    if "TOOL_CALL" not in skip:
        for c in t.get("tool_calls") or []:
            n = c.get("n")
            if not isinstance(n, int) or n in printed_calls:
                continue
            printed_calls.add(n)
            res = c.get("result") or {}
            status = res.get("status", "?")
            args = json.dumps(c.get("arguments") or {}, separators=(",", ":"))[:80]
            out.append(Event(c.get("at", ""), inc, "TOOL_CALL",
                             f"#{n} {c.get('tool')}({args}) -> {status}: {str(res.get('summary', ''))[:110]}",
                             STATUS_COLOURS.get(status, "")))
    if t.get("finished_at") is None:
        return out
    end = t.get("finished_at", "")
    if "MODEL_NOTE" not in skip:
        out += [Event(end, inc, "MODEL_NOTE", str(note)[:200]) for note in t.get("model_notes") or []]
    diag = t.get("diagnosis") or {}
    root = diag.get("root_cause") or {}
    if "DIAGNOSIS" not in skip and diag:
        impacted = ", ".join(diag.get("impacted_services") or []) or "none"
        out.append(Event(end, inc, "DIAGNOSIS",
                         f"root cause {root.get('service') or '?'}/{root.get('category') or '?'}; impacted: "
                         f"{impacted}; model confidence {diag.get('confidence', '?')}"))
    gate = t.get("gate") or {}
    if "GATE" not in skip and gate:
        reasons = "; ".join(gate.get("reasons") or [])
        out.append(Event(end, inc, "GATE",
                         f"final confidence {gate.get('final_confidence')}, "
                         f"{'ESCALATE to a human' if gate.get('escalate') else 'no escalation'}, "
                         f"citations {gate.get('valid_citations', 0)} valid / {gate.get('invalid_citations', 0)} "
                         f"invalid" + (f" ({reasons[:120]})" if reasons else ""),
                         YELLOW if gate.get("escalate") else GREEN))
    out += [Event(end, inc, "ERROR", str(e)[:200]) for e in t.get("errors") or []]
    if "REPORT_WRITTEN" not in skip and t.get("report") is not None:
        valid = t.get("report_schema_valid")
        out.append(Event(end, inc, "REPORT_WRITTEN",
                         f"report.json written, schema {'valid' if valid else 'INVALID'}", _good_or_bad(valid)))
    return out


class LineTail:
    """Reads complete new lines from a file that may not exist yet or may be rewritten."""

    def __init__(self, path: Path, from_start: bool) -> None:
        self.path = path
        self.offset = 0 if from_start or not path.exists() else path.stat().st_size
        self.buffer = ""

    def read_lines(self) -> List[str]:
        try:
            size = self.path.stat().st_size
            if size < self.offset:
                self.offset, self.buffer = 0, ""
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.offset)
                chunk = f.read()
                self.offset = f.tell()
        except OSError:
            return []
        lines = (self.buffer + chunk).split("\n")
        self.buffer = lines.pop()
        return [ln for ln in lines if ln.strip()]


@dataclass
class IncidentState:
    run_log: LineTail
    transcript_mtime: float = 0.0
    printed_calls: Set[int] = field(default_factory=set)
    done: bool = False


class Watcher:
    def __init__(self, audit_log: Path, output_dir: Path, incident: Optional[str] = None,
                 from_start: bool = False, colour: bool = True,
                 write: Callable[[str], None] = print) -> None:
        self.audit = LineTail(audit_log, from_start)
        self.output_dir = output_dir
        self.incident = incident
        self.from_start = from_start
        self.colour = colour
        self.write = write
        self.started = time.time()
        self.streamed: Dict[str, Set[str]] = {}
        self.incidents: Dict[str, IncidentState] = {}
        if incident:
            self._track(incident)

    def _track(self, incident_id: str) -> None:
        if incident_id and incident_id not in self.incidents:
            self.incidents[incident_id] = IncidentState(LineTail(self.output_dir / incident_id / "run.log", True))

    def render(self, ev: Event) -> str:
        label, base = EVENT_STYLES.get(ev.event, (ev.event, ""))
        colour = ev.colour or base
        line = f"{_short_time(ev.ts):8s}  {ev.incident_id[:22]:22s}  {label:11s}  {ev.summary}"
        return f"{colour}{line}{RESET}" if self.colour and colour else line

    def _emit(self, events: Iterable[Event]) -> None:
        for ev in events:
            self.write(self.render(ev))

    def _discover(self) -> None:
        """Without --incident, also follow incidents that start writing files after the watcher started."""
        if self.incident or not self.output_dir.is_dir():
            return
        for d in self.output_dir.iterdir():
            if d.name in self.incidents or not d.is_dir():
                continue
            files = [d / "transcript.json", d / "run.log"]
            if any(f.exists() and f.stat().st_mtime >= self.started for f in files):
                self._track(d.name)

    def poll(self) -> None:
        for line in self.audit.read_lines():
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict):
                    raise ValueError("not an object")
            except ValueError:
                self._emit([Event("", "", "LOG", f"unparsed audit line: {line[:160]}")])
                continue
            ev = audit_event(raw)
            if self.incident and ev.incident_id != self.incident:
                continue
            self.streamed.setdefault(ev.incident_id, set()).add(ev.event)
            self._track(ev.incident_id)
            self._emit([ev])
        self._discover()
        # src/events.py writes each event to the audit log before run.log, so run.log is only a fallback.
        use_run_log = not self.audit.path.exists()
        for inc, state in self.incidents.items():
            if use_run_log:
                self._emit(Event("", inc, "LOG", ln) for ln in state.run_log.read_lines())
            self._poll_transcript(inc, state)

    def _poll_transcript(self, inc: str, state: IncidentState) -> None:
        path = self.output_dir / inc / "transcript.json"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if state.done or mtime == state.transcript_mtime:
            return
        try:
            t = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        state.transcript_mtime = mtime
        self._emit(transcript_events(t, self.streamed.get(inc, set()), state.printed_calls))
        state.done = t.get("finished_at") is not None


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python scripts/watch_run.py", description=__doc__.splitlines()[0])
    p.add_argument("--incident", help="Follow only this incident id.")
    p.add_argument("--from-start", action="store_true", help="Replay the existing audit log first.")
    p.add_argument("--once", action="store_true", help="Print what exists now and exit.")
    p.add_argument("--no-color", action="store_true", help="Plain text output.")
    p.add_argument("--audit-log", type=Path, help="Default: AUDIT_LOG_PATH, else audit_logs/audit.jsonl.")
    p.add_argument("--output-dir", type=Path, help="Default: REPORT_OUTPUT_DIR, else incident_output.")
    p.add_argument("--interval", type=float, default=0.5, help="Seconds between polls (default 0.5).")
    args = p.parse_args(argv)

    def resolve(given: Optional[Path], env: str, default: str) -> Path:
        path = given or Path(os.environ.get(env) or default)
        return path if path.is_absolute() else ROOT / path

    audit_log = resolve(args.audit_log, "AUDIT_LOG_PATH", "audit_logs/audit.jsonl")
    output_dir = resolve(args.output_dir, "REPORT_OUTPUT_DIR", "incident_output")
    colour = not args.no_color and not os.environ.get("NO_COLOR") and sys.stdout.isatty()
    watcher = Watcher(audit_log, output_dir, incident=args.incident, from_start=args.from_start or args.once,
                      colour=colour, write=lambda s: print(s, flush=True))
    if args.once:
        watcher.poll()
        return 0
    print(f"Watching {audit_log} and {output_dir} (Ctrl-C to stop)", flush=True)
    if not audit_log.exists():
        print("  audit log does not exist yet; waiting for the first event", flush=True)
    try:
        while True:
            watcher.poll()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
