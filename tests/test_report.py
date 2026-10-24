"""finalize(), report.json / report.md and the `python -m oncall.report` CLI (offline)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from oncall import schema as S
from oncall.report import finalize, finalize_run_dir, main
from oncall.validator import load_ledger

LEDGERS = Path(__file__).parent / "fixtures" / "ledgers"
REPO = Path(__file__).resolve().parent.parent
RUN_INFO = {"incident_id": "inc-test-0001", "started_at": "2026-10-24T10:00:00+00:00",
            "trigger": "Customers report errors.", "budget_exhausted": False, "llm_error": None,
            "stop_reason": "submitted"}


def good_candidate():
    """A candidate on the container-fault ledger with two kinds of evidence and one alternative."""
    return {
        "component": "valkey-cart", "cause": "The cart's cache container has exited.", "stated_confidence": 0.9,
        "evidence": [
            {"ledger_id": "C1", "kind": "container", "claim": "valkey-cart exited", "quote": "valkey-cart", "value": "exited"},
            {"ledger_id": "L1", "kind": "log", "claim": "cart cannot reach its cache", "quote": "Connection failed. Disposing the object"},
        ],
        "alternatives_considered": [{"hypothesis": "cart bug", "why_rejected": "cache container is down"}],
        "investigation_steps": [{"tool": "container_health", "finding": "valkey-cart exited", "ledger_id": "C1"}],
        "limitations": ["no memory history checked"],
    }


def make_run(tmp_path, candidate, ledger_file="live_container_fault.json", run_info=RUN_INFO):
    folder = tmp_path / "run"
    folder.mkdir()
    shutil.copy(LEDGERS / ledger_file, folder / S.LEDGER_FILE)
    (folder / S.CANDIDATE_FILE).write_text(json.dumps(candidate), encoding="utf-8")
    (folder / S.RUN_INFO_FILE).write_text(json.dumps(run_info), encoding="utf-8")
    return folder


def test_diagnosed_report_has_every_field_and_both_files(tmp_path):
    ledger = load_ledger(LEDGERS / "live_container_fault.json")
    report = finalize(good_candidate(), ledger, RUN_INFO, tmp_path / "out")
    assert list(report) == list(S.REPORT_FIELDS)
    assert report[S.STATUS] == S.STATUS_DIAGNOSED
    assert report[S.ESCALATION_REASON] is None
    assert report[S.CONFIDENCE] == 0.9 and report[S.STATED_CONFIDENCE] == 0.9
    assert report[S.INCIDENT_ID] == "inc-test-0001" and report[S.TRIGGER] == "Customers report errors."
    assert all(e[S.EV_VALIDATED] for e in report[S.EVIDENCE])
    assert report[S.STEPS] and report[S.LIMITATIONS] == ["no memory history checked"]
    on_disk = json.loads((tmp_path / "out" / S.REPORT_JSON_FILE).read_text(encoding="utf-8"))
    assert on_disk == report
    assert (tmp_path / "out" / S.REPORT_MD_FILE).read_text(encoding="utf-8").startswith("# Incident inc-test-0001")


def test_every_evidence_item_carries_validated_and_a_note(tmp_path):
    report = finalize(good_candidate(), load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    for item in report[S.EVIDENCE]:
        assert set(item) == set(S.EVIDENCE_FIELDS)
        assert isinstance(item[S.EV_VALIDATED], bool) and item[S.EV_NOTE]


def test_invented_quote_escalates_but_keeps_everything_found(tmp_path):
    cand = good_candidate()
    cand["evidence"][1]["quote"] = "a log line nobody wrote"
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED
    assert "failed validation" in report[S.ESCALATION_REASON]
    assert report[S.COMPONENT] == "valkey-cart" and report[S.CAUSE]
    assert [e[S.EV_VALIDATED] for e in report[S.EVIDENCE]] == [True, False]
    assert report[S.ALTERNATIVES] and report[S.STEPS]


def test_low_confidence_escalates_with_the_threshold_in_the_reason(tmp_path):
    cand = good_candidate()
    cand["stated_confidence"] = 0.4
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED and "threshold" in report[S.ESCALATION_REASON]


def test_caps_appear_in_confidence_reasons(tmp_path):
    cand = good_candidate()
    cand["evidence"] = cand["evidence"][:1]
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    assert report[S.CONFIDENCE] == 0.6 < report[S.STATED_CONFIDENCE]
    assert any("capped at 0.60" in r for r in report[S.CONFIDENCE_REASONS])


def test_budget_exhausted_run_escalates(tmp_path):
    info = dict(RUN_INFO, budget_exhausted=True, stop_reason="step_budget")
    report = finalize(good_candidate(), load_ledger(LEDGERS / "live_container_fault.json"), info, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED and "budget" in report[S.ESCALATION_REASON]


def test_unknown_candidate_with_no_evidence_escalates(tmp_path):
    cand = {"component": "unknown", "cause": "No diagnosis was produced.", "stated_confidence": 0.0,
            "evidence": [], "alternatives_considered": [], "investigation_steps": [], "limitations": ["ran out of steps"]}
    report = finalize(cand, load_ledger(LEDGERS / "live_healthy.json"), RUN_INFO, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED and report[S.CONFIDENCE] == 0.0 and report[S.EVIDENCE] == []
    assert "ran out of steps" in (tmp_path / S.REPORT_MD_FILE).read_text(encoding="utf-8")


def test_missing_run_info_still_produces_a_report(tmp_path):
    report = finalize(good_candidate(), load_ledger(LEDGERS / "live_container_fault.json"), None, tmp_path)
    assert report[S.INCIDENT_ID] is None and report[S.STATUS] == S.STATUS_DIAGNOSED


def test_out_dir_is_created(tmp_path):
    target = tmp_path / "deep" / "er" / "folder"
    finalize(good_candidate(), load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, target)
    assert (target / S.REPORT_JSON_FILE).exists()


def test_input_files_of_a_run_are_not_modified(tmp_path):
    folder = make_run(tmp_path, good_candidate())
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    finalize_run_dir(folder)
    for name, content in before.items():
        assert (folder / name).read_bytes() == content


def test_markdown_shows_marks_confidence_and_what_was_not_checked(tmp_path):
    cand = good_candidate()
    cand["evidence"][1]["quote"] = "a log line nobody wrote"
    finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    md = (tmp_path / S.REPORT_MD_FILE).read_text(encoding="utf-8")
    assert "ESCALATED" in md and "✓" in md and "✗" in md
    assert "## Confidence" in md and "Final: 0.60 (the agent stated 0.9)" in md
    assert "## What was not checked" in md and "no memory history checked" in md
    assert "Alternatives ruled out" in md


# --- CLI ----------------------------------------------------------------------------------------

def test_cli_main_writes_both_files_into_the_run_folder(tmp_path, capsys):
    folder = make_run(tmp_path, good_candidate())
    assert main([str(folder)]) == 0
    assert (folder / S.REPORT_JSON_FILE).exists() and (folder / S.REPORT_MD_FILE).exists()
    out = capsys.readouterr().out
    assert "DIAGNOSED" in out and "valkey-cart" in out


def test_cli_prints_the_escalation_reason(tmp_path, capsys):
    cand = good_candidate()
    cand["stated_confidence"] = 0.3
    folder = make_run(tmp_path, cand)
    assert main([str(folder)]) == 0
    assert "escalation reason" in capsys.readouterr().out


def test_cli_reports_a_missing_file_without_a_traceback(tmp_path, capsys):
    folder = make_run(tmp_path, good_candidate())
    (folder / S.CANDIDATE_FILE).unlink()
    assert main([str(folder)]) == 2
    assert "cannot build a report" in capsys.readouterr().err


def test_cli_reports_invalid_json(tmp_path, capsys):
    folder = make_run(tmp_path, good_candidate())
    (folder / S.RUN_INFO_FILE).write_text("{not json", encoding="utf-8")
    assert main([str(folder)]) == 2


def test_module_runs_as_python_dash_m(tmp_path):
    folder = make_run(tmp_path, good_candidate())
    done = subprocess.run([sys.executable, "-m", "oncall.report", str(folder)], cwd=REPO,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (folder / S.REPORT_JSON_FILE).exists()


def test_report_works_on_a_ledger_saved_by_the_real_ledger_class(tmp_path):
    """The saved ledger.json is a list of entries; load_ledger also accepts the in-memory list/dict."""
    entries = json.loads((LEDGERS / "live_flag_fault.json").read_text(encoding="utf-8"))
    cand = {"component": "payment", "cause": "payment charges fail", "stated_confidence": 0.85,
            "evidence": [
                {"ledger_id": "L1", "kind": "log", "claim": "payment errors", "quote": entries[3]["result"]["items"][0]["message"]},
                {"ledger_id": "M1", "kind": "metric", "claim": "payment errors 100%", "quote": "100.0"}],
            "alternatives_considered": [{"hypothesis": "network", "why_rejected": "no connection errors"}],
            "investigation_steps": [], "limitations": []}
    report = finalize(cand, entries, RUN_INFO, tmp_path)
    assert report[S.STATUS] == S.STATUS_DIAGNOSED and report[S.CONFIDENCE] == 0.85
