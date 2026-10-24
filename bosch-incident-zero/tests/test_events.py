import io
import json
from pathlib import Path

import pytest

from src.events import EVENTS, EventLog, format_line, read_events


def _lines(path: Path):
    return [json.loads(x) for x in path.read_text().splitlines()]


def test_events_are_appended_in_order_with_contract_fields(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    log = EventLog(audit, incident_id="INC-1", echo=False)
    log.emit("ALERT_RECEIVED", "alert in", {"alert": "errors on checkout"})
    log.emit("TOOL_CALL", "system_overview -> ok", {"tool": "system_overview", "status": "ok"})
    log.emit("GATE", "escalate=no", {"escalate": False})

    recs = _lines(audit)
    assert [r["event"] for r in recs] == ["ALERT_RECEIVED", "TOOL_CALL", "GATE"]
    for r in recs:
        assert set(r) == {"ts", "incident_id", "event", "summary", "data"}
        assert r["incident_id"] == "INC-1"
    assert [r["ts"] for r in recs] == sorted(r["ts"] for r in recs)


def test_unknown_event_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        EventLog(echo=False).emit("ACTION_DONE", "typo")


def test_secrets_are_never_written(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    key = "sk-or-v1-" + "a" * 40
    log = EventLog(audit, incident_id="INC-2", echo=False)
    log.emit("ERROR", f"call failed with key {key}", {
        "LLM_API_KEY": key, "headers": {"Authorization": "Bearer abcdefghijkl", "x-api-key": "zzz"},
        "csrf_token": "t0ken", "note": f"used {key}", "usage": {"prompt_tokens": 12, "total_tokens": 20},
    })
    text = audit.read_text()
    assert key not in text and "abcdefghijkl" not in text and "t0ken" not in text and "zzz" not in text
    data = _lines(audit)[0]["data"]
    assert data["usage"] == {"prompt_tokens": 12, "total_tokens": 20}


def test_flag_data_is_dropped(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "audit.jsonl", echo=False)
    rec = log.emit("TOOL_CALL", "search_traces -> ok", {
        "attributes": [{"key": "feature_flag.key", "value": "paymentFailure"}, {"key": "rpc.method", "value": "Charge"}],
        "flagd_state": {"x": 1},
    })
    dumped = json.dumps(rec)
    assert "paymentFailure" not in dumped and "flagd_state" not in dumped
    assert "Charge" in dumped


def test_run_log_written_after_bind_and_quiet_still_writes_files(tmp_path: Path, capsys) -> None:
    audit = tmp_path / "audit.jsonl"
    log = EventLog(audit, run_log_dir=tmp_path / "out", echo=False)
    log.bind("INC-3")
    log.emit("DIAGNOSIS", "payment / dependency_failure (high)", {"service": "payment"})
    assert capsys.readouterr().out == ""
    run_log = tmp_path / "out" / "INC-3" / "run.log"
    assert run_log.read_text().strip().endswith("DIAGNOSIS          payment / dependency_failure (high)")
    assert _lines(audit)[0]["event"] == "DIAGNOSIS"


def test_echo_prints_one_timestamped_line_per_event() -> None:
    buf = io.StringIO()
    log = EventLog(echo=True, stream=buf)
    rec = log.emit("PLAN", "RESTART_SERVICE on payment")
    assert buf.getvalue() == format_line(rec) + "\n"
    assert buf.getvalue()[12] == "Z"


def test_from_settings_resolves_relative_paths(tmp_path: Path) -> None:
    class S:
        root_dir = tmp_path
        audit_log_path = "./audit_logs/audit.jsonl"
        report_output_dir = "./incident_output"

    log = EventLog.from_settings(S(), echo=False, incident_id="INC-4")
    assert log.audit_log_path == tmp_path / "audit_logs" / "audit.jsonl"
    assert log.run_log_path == tmp_path / "incident_output" / "INC-4" / "run.log"


def test_read_events_filters_by_incident_and_skips_old_format(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    audit.write_text(json.dumps({"timestamp": "old", "event": "ACTION_EXECUTED_DRY_RUN"}) + "\nnot json\n")
    a = EventLog(audit, incident_id="A", echo=False)
    b = EventLog(audit, incident_id="B", echo=False)
    a.emit("ALERT_RECEIVED", "a1")
    b.emit("ALERT_RECEIVED", "b1")
    a.emit("GATE", "a2")

    recs, n = read_events(audit, incident_id="A")
    assert [r["summary"] for r in recs] == ["a1", "a2"] and n == 5
    a.emit("REPORT_WRITTEN", "a3")
    more, n2 = read_events(audit, incident_id="A", after_line=n)
    assert [r["summary"] for r in more] == ["a3"] and n2 == 6


def test_contract_event_names() -> None:
    required = {"ALERT_RECEIVED", "TOOL_CALL", "MODEL_NOTE", "DIAGNOSIS", "GATE", "PLAN", "APPROVAL_REQUESTED",
                "APPROVAL_DECISION", "ACTION_EXECUTED", "DRY_RUN", "VERIFICATION", "ROLLBACK", "KILL_SWITCH",
                "REPORT_WRITTEN"}
    assert required <= EVENTS
