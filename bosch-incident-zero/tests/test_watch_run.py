"""Live run follower: audit log tailing, transcript rendering, robustness against partial files."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "watch_run", Path(__file__).resolve().parents[1] / "scripts" / "watch_run.py")
wr = importlib.util.module_from_spec(_SPEC)
sys.modules["watch_run"] = wr
_SPEC.loader.exec_module(wr)


def transcript(incident_id="INC-1", finished=True):
    return {
        "incident_id": incident_id, "alert": "Error rate above 5% on checkout",
        "started_at": "2026-10-24T04:00:00+00:00",
        "tool_calls": [
            {"n": 1, "at": "2026-10-24T04:00:01+00:00", "tool": "system_overview", "arguments": {"window_minutes": 15},
             "result": {"status": "ok", "summary": "1 service(s) flagged: checkout"}},
            {"n": 2, "at": "2026-10-24T04:00:02+00:00", "tool": "deploy_history", "arguments": {},
             "result": {"status": "source_unavailable", "summary": "no deploy source"}},
        ],
        "model_notes": ["checkout calls to payment never arrive"],
        "diagnosis": {"root_cause": {"service": "payment", "category": "dependency_unreachable"},
                      "impacted_services": ["checkout", "frontend"], "confidence": "high"},
        "gate": {"final_confidence": "high", "escalate": False, "valid_citations": 5, "invalid_citations": 0,
                 "reasons": []},
        "report": {"incident_id": incident_id}, "report_schema_valid": True, "errors": [],
        "finished_at": "2026-10-24T04:01:00+00:00" if finished else None,
    }


def make_run(tmp_path, audit_lines=(), t=None, run_log=None, incident_id="INC-1"):
    audit = tmp_path / "audit_logs" / "audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text("".join(audit_lines))
    out = tmp_path / "incident_output"
    run_dir = out / incident_id
    run_dir.mkdir(parents=True)
    if t is not None:
        (run_dir / "transcript.json").write_text(json.dumps(t))
    if run_log is not None:
        (run_dir / "run.log").write_text(run_log)
    return audit, out


def watch(audit, out, **kw):
    lines = []
    w = wr.Watcher(audit, out, colour=False, write=lines.append, **kw)
    return w, lines


def jl(obj):
    return json.dumps(obj) + "\n"


def test_once_renders_legacy_audit_events_and_their_transcript(tmp_path):
    audit, out = make_run(tmp_path, [
        jl({"timestamp": "2026-10-24T04:01:05+00:00", "event": "ACTION_EXECUTED_DRY_RUN", "incident_id": "INC-1",
            "action_type": "RESTART_SERVICE", "target_service": "payment", "dry_run": True}),
    ], t=transcript())
    w, lines = watch(audit, out, from_start=True)
    w.poll()
    text = "\n".join(lines)
    for expected in ("DRY RUN", "action_type=RESTART_SERVICE", "ALERT", "Error rate above 5% on checkout",
                     "#1 system_overview", "-> ok", "#2 deploy_history", "source_unavailable",
                     "root cause payment/dependency_unreachable", "impacted: checkout, frontend",
                     "final confidence high", "no escalation", "schema valid", "checkout calls to payment"):
        assert expected in text, expected


def test_new_contract_events_render_their_summary_and_skip_duplicates(tmp_path):
    audit, out = make_run(tmp_path, [
        jl({"ts": "2026-10-24T04:00:01+00:00", "incident_id": "INC-1", "event": "TOOL_CALL",
            "summary": "system_overview -> ok", "data": {"tool": "system_overview", "status": "ok"}}),
        jl({"ts": "2026-10-24T04:01:02+00:00", "incident_id": "INC-1", "event": "APPROVAL_DECISION",
            "summary": "operator approved RESTART_SERVICE on payment", "data": {"decision": "APPROVED"}}),
    ], t=transcript())
    w, lines = watch(audit, out, from_start=True)
    w.poll()
    text = "\n".join(lines)
    assert "system_overview -> ok" in text and "operator approved" in text
    assert "#1 system_overview" not in text  # tool calls already streamed through the audit log
    assert "root cause payment" in text


def test_unknown_event_is_rendered_generically(tmp_path):
    audit, out = make_run(tmp_path, [jl({"timestamp": "x", "event": "SOMETHING_NEW", "incident_id": "INC-1",
                                         "foo": "bar"})])
    w, lines = watch(audit, out, from_start=True)
    w.poll()
    assert any("SOMETHING_NEW" in ln and "foo=bar" in ln for ln in lines)


def test_partial_last_line_waits_for_completion(tmp_path):
    full = jl({"ts": "2026-10-24T04:00:00+00:00", "incident_id": "INC-1", "event": "ALERT_RECEIVED",
               "summary": "first"})
    audit, out = make_run(tmp_path, [full, '{"ts": "2026-10-24T04:00:01+00:00", "event": "PLA'])
    w, lines = watch(audit, out, from_start=True)
    w.poll()
    assert len(lines) == 1 and "first" in lines[0]
    with open(audit, "a") as f:
        f.write('N", "incident_id": "INC-1", "summary": "restart payment"}\n')
    w.poll()
    assert len(lines) == 2 and "PLAN" in lines[1] and "restart payment" in lines[1]


def test_garbage_line_does_not_crash(tmp_path):
    audit, out = make_run(tmp_path, ["not json at all\n", "[1, 2]\n"])
    w, lines = watch(audit, out, from_start=True)
    w.poll()
    assert len(lines) == 2 and all("unparsed audit line" in ln for ln in lines)


def test_missing_files_are_fine_and_picked_up_later(tmp_path):
    audit = tmp_path / "nope" / "audit.jsonl"
    out = tmp_path / "incident_output"
    w, lines = watch(audit, out, incident="INC-9")
    w.poll()
    assert lines == []
    (out / "INC-9").mkdir(parents=True)
    (out / "INC-9" / "transcript.json").write_text(json.dumps(transcript("INC-9"))[:50])  # caught mid-write
    w.poll()
    assert lines == []
    (out / "INC-9" / "transcript.json").write_text(json.dumps(transcript("INC-9")))
    w.poll()
    assert any("root cause payment" in ln for ln in lines)
    count = len(lines)
    w.poll()
    assert len(lines) == count  # nothing is printed twice


def test_incident_filter_and_no_run_log_duplicates(tmp_path):
    audit, out = make_run(tmp_path, [
        jl({"ts": "2026-10-24T04:00:00+00:00", "incident_id": "OTHER", "event": "ALERT_RECEIVED", "summary": "x"}),
        jl({"ts": "2026-10-24T04:00:00+00:00", "incident_id": "INC-1", "event": "PLAN", "summary": "mine"}),
    ], run_log="04:00:00.000Z PLAN               mine\n")
    w, lines = watch(audit, out, incident="INC-1", from_start=True)
    w.poll()
    assert len(lines) == 1 and "mine" in lines[0] and "OTHER" not in lines[0]


def test_run_log_is_the_fallback_without_an_audit_log(tmp_path):
    out = tmp_path / "incident_output"
    (out / "INC-1").mkdir(parents=True)
    (out / "INC-1" / "run.log").write_text("04:00:00.000Z TOOL_CALL          #1 system_overview -> ok\n")
    w, lines = watch(tmp_path / "missing.jsonl", out, incident="INC-1")
    w.poll()
    assert len(lines) == 1 and "system_overview -> ok" in lines[0]


def test_follow_mode_skips_old_events_but_shows_new_runs(tmp_path):
    audit, out = make_run(tmp_path, [jl({"ts": "t", "incident_id": "OLD", "event": "PLAN", "summary": "old"})])
    w, lines = watch(audit, out)
    w.poll()
    assert lines == []
    (out / "NEW-1").mkdir()
    (out / "NEW-1" / "transcript.json").write_text(json.dumps(transcript("NEW-1")))
    w.poll()
    assert any("NEW-1" in ln and "root cause payment" in ln for ln in lines)


def test_escalation_and_errors_are_visible():
    t = transcript()
    t["gate"] = {"final_confidence": "low", "escalate": True, "reasons": ["only 1 validated evidence item"]}
    t["errors"] = ["LLM failure: daily quota exceeded"]
    events = wr.transcript_events(t, set(), set())
    names = [e.event for e in events]
    assert "ERROR" in names
    gate = next(e for e in events if e.event == "GATE")
    assert "ESCALATE" in gate.summary and gate.colour == wr.YELLOW


def test_colour_codes_only_when_enabled(tmp_path):
    ev = wr.Event("2026-10-24T04:00:00+00:00", "INC-1", "KILL_SWITCH", "engaged")
    plain = wr.Watcher(tmp_path / "a", tmp_path / "o", colour=False).render(ev)
    coloured = wr.Watcher(tmp_path / "a", tmp_path / "o", colour=True).render(ev)
    assert "\033[" not in plain and "KILL SWITCH" in plain
    assert coloured.startswith(wr.BOLD + wr.RED) and coloured.endswith(wr.RESET)


def test_cli_once_exits_cleanly(tmp_path, capsys):
    audit, out = make_run(tmp_path, [jl({"ts": "2026-10-24T04:00:00+00:00", "incident_id": "INC-1",
                                         "event": "KILL_SWITCH", "summary": "engaged by operator"})])
    assert wr.main(["--once", "--no-color", "--audit-log", str(audit), "--output-dir", str(out)]) == 0
    assert "engaged by operator" in capsys.readouterr().out


@pytest.mark.parametrize("decision, colour", [("APPROVED", wr.GREEN), ("REJECTED", wr.RED), ("", wr.YELLOW)])
def test_approval_decision_colour(decision, colour):
    ev = wr.audit_event({"event": "APPROVAL_DECISION", "incident_id": "I", "data": {"decision": decision}})
    assert ev.colour == colour


@pytest.mark.parametrize("event, data, colour", [
    ("APPROVAL_DECISION", {"approved": True}, wr.GREEN),
    ("APPROVAL_DECISION", {"approved": False}, wr.RED),
    ("VERIFICATION", {"status": "RECOVERED", "recovered": True}, wr.GREEN),
    ("VERIFICATION", {"status": "NOT_RECOVERED", "recovered": False}, wr.RED),
    ("VERIFICATION", {"status": "NOT_VERIFIED_DRY_RUN", "recovered": False}, wr.YELLOW),
    ("KILL_SWITCH", {"checkpoint": "plan", "engaged": False}, wr.DIM),
    ("KILL_SWITCH", {"checkpoint": "pre_execute", "engaged": True}, wr.BOLD + wr.RED),
    ("TOOL_CALL", {"status": "ok"}, wr.DIM),
    ("TOOL_CALL", {"status": "source_unavailable"}, wr.RED),
])
def test_contract_event_colours(event, data, colour):
    assert wr.audit_event({"ts": "t", "event": event, "incident_id": "I", "summary": "s", "data": data}).colour \
        == colour


def test_worker_a_investigation_events(tmp_path):
    usage = {"requests": 4, "prompt_tokens": 1200, "completion_tokens": 300, "total_tokens": 1500}
    audit, out = make_run(tmp_path, [
        jl({"ts": "2026-10-24T05:00:00.000+00:00", "incident_id": "INC-1", "event": "ALERT_RECEIVED",
            "summary": "Error rate above 5% on checkout", "data": {"alert": "Error rate above 5% on checkout"}}),
        jl({"ts": "2026-10-24T05:00:01.000+00:00", "incident_id": "INC-1", "event": "TOOL_CALL",
            "summary": "#1 system_overview({}) -> no_data: nothing", "data": {"n": 1, "status": "no_data"}}),
        jl({"ts": "2026-10-24T05:00:02.000+00:00", "incident_id": "INC-1", "event": "MODEL_NOTE",
            "summary": "checking payment", "data": {"text": "checking payment"}}),
        jl({"ts": "2026-10-24T05:00:03.000+00:00", "incident_id": "INC-1", "event": "DIAGNOSIS",
            "summary": "payment/dependency_unreachable", "data": {"verdict": "diagnosed", "token_usage": usage}}),
        jl({"ts": "2026-10-24T05:00:04.000+00:00", "incident_id": "INC-1", "event": "GATE",
            "summary": "escalate=True confidence=low tokens=1500",
            "data": {"escalate": True, "final_confidence": "low", "token_usage": usage}}),
        jl({"ts": "2026-10-24T05:00:05.000+00:00", "incident_id": "INC-1", "event": "ERROR",
            "summary": "search_logs failed", "data": {"source": "tool", "error": "timeout", "tool": "search_logs"}}),
        jl({"ts": "2026-10-24T05:00:06.000+00:00", "incident_id": "INC-1", "event": "ACTION_REFUSED",
            "summary": "no action on escalation", "data": {"reason": "escalated"}}),
    ], t=transcript())
    events = []
    w = wr.Watcher(audit, out, colour=False, write=lambda s: None, from_start=True)
    w._emit = lambda evs: events.extend(evs)
    w.poll()
    by = {e.event: e for e in events}
    assert by["TOOL_CALL"].colour == wr.YELLOW
    assert by["DIAGNOSIS"].summary.endswith("(tokens in/out 1200/300)")
    assert "tokens in/out" not in by["GATE"].summary and by["GATE"].colour == wr.YELLOW
    assert by["ERROR"].colour == wr.BOLD + wr.RED and by["ACTION_REFUSED"].colour == wr.RED
    assert [e.event for e in events].count("TOOL_CALL") == 1  # transcript copy skipped


@pytest.mark.parametrize("summary, review, expected, absent", [
    ("escalate=True confidence=low review=refuted tokens=1500",
     {"verdict": "refuted", "confidence_before": "high", "confidence_after": "low"},
     "review=refuted tokens=1500 (confidence high -> low)", "tokens in/out"),
    ("escalate=False confidence=high review=upheld tokens=900",
     {"verdict": "upheld", "confidence_before": "high", "confidence_after": "high"},
     "review=upheld tokens=900", "->"),
    ("escalate=False confidence=medium",
     {"verdict": "weakened", "confidence_before": "high", "confidence_after": "medium"},
     "review weakened (confidence high -> medium)", "review=weakened"),
])
def test_gate_line_shows_review(summary, review, expected, absent):
    ev = wr.audit_event({"ts": "t", "incident_id": "I", "event": "GATE", "summary": summary,
                         "data": {"escalate": False, "final_confidence": "x", "review": review,
                                  "token_usage": {"prompt_tokens": 1, "completion_tokens": 2}}})
    assert expected in ev.summary and absent not in ev.summary
    assert ev.summary.count("tokens") <= 1
