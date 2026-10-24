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


def test_budget_exhausted_run_with_validated_evidence_of_two_kinds_is_diagnosed(tmp_path):
    info = dict(RUN_INFO, budget_exhausted=True, stop_reason="step_budget")
    report = finalize(good_candidate(), load_ledger(LEDGERS / "live_container_fault.json"), info, tmp_path)
    assert report[S.STATUS] == S.STATUS_DIAGNOSED and "step budget was reached" in report[S.CONFIDENCE_REASONS]


def test_budget_exhausted_run_without_validated_evidence_escalates(tmp_path):
    info = dict(RUN_INFO, budget_exhausted=True, stop_reason="step_budget")
    cand = good_candidate()
    cand["evidence"] = []
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), info, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED and "budget" in report[S.ESCALATION_REASON]


def test_unknown_candidate_with_no_evidence_escalates(tmp_path):
    cand = {"component": "unknown", "cause": "No diagnosis was produced.", "stated_confidence": 0.0,
            "evidence": [], "alternatives_considered": [], "investigation_steps": [], "limitations": ["ran out of steps"]}
    report = finalize(cand, load_ledger(LEDGERS / "live_healthy.json"), RUN_INFO, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED and report[S.CONFIDENCE] == 0.0 and report[S.EVIDENCE] == []
    assert "ran out of steps" in (tmp_path / S.REPORT_MD_FILE).read_text(encoding="utf-8")


def test_missing_or_empty_run_info_escalates_so_it_never_looks_clean(tmp_path):
    ledger = load_ledger(LEDGERS / "live_container_fault.json")
    for info in (None, {}, [], "text"):
        report = finalize(good_candidate(), ledger, info, tmp_path)
        assert report[S.INCIDENT_ID] is None and report[S.STATUS] == S.STATUS_ESCALATED
        assert "run info missing" in report[S.ESCALATION_REASON]


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


def test_cli_reports_a_missing_folder_without_a_traceback(tmp_path, capsys):
    assert main([str(tmp_path / "nope")]) == 2
    assert "cannot build a report" in capsys.readouterr().err
    assert not (tmp_path / "nope").exists()


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


# --- escalation reason names the caps -----------------------------------------------------------

def test_single_kind_escalation_reason_names_the_cap(tmp_path):
    cand = good_candidate()
    cand["evidence"] = cand["evidence"][:1]
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED
    assert "only one kind of evidence (capped at 0.60), below the 0.70 threshold" in report[S.ESCALATION_REASON]


# --- the kind comes from the ledger, not the label ----------------------------------------------

def test_two_items_on_one_entry_with_different_labels_are_capped_and_escalated(tmp_path):
    cand = good_candidate()
    cand["evidence"] = [
        {"ledger_id": "C1", "kind": "container", "claim": "exited", "quote": "valkey-cart"},
        {"ledger_id": "C1", "kind": "log", "claim": "also exited", "quote": "exited"}]
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    assert report[S.CONFIDENCE] == 0.6 and report[S.STATUS] == S.STATUS_ESCALATED


def test_mismatched_label_is_kept_with_a_note_on_the_item_and_a_confidence_reason(tmp_path):
    cand = good_candidate()
    cand["evidence"][0]["kind"] = "trace"
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    first = report[S.EVIDENCE][0]
    assert first[S.EV_VALIDATED] and first[S.EV_KIND] == "trace"
    assert "labelled kind trace but cites a container entry" in first[S.EV_NOTE]
    assert "evidence C1 labelled kind trace but cites a container entry" in report[S.CONFIDENCE_REASONS]


# --- bad input never crashes and never half-writes ----------------------------------------------

def run_files(folder):
    return sorted(p.name for p in folder.iterdir())


def test_null_json_in_each_file_gives_an_escalated_report(tmp_path):
    for name in (S.LEDGER_FILE, S.CANDIDATE_FILE, S.RUN_INFO_FILE):
        folder = tmp_path / name.split(".")[0]
        folder.mkdir()
        for other, content in ((S.LEDGER_FILE, (LEDGERS / "live_container_fault.json").read_text()),
                               (S.CANDIDATE_FILE, json.dumps(good_candidate())),
                               (S.RUN_INFO_FILE, json.dumps(RUN_INFO))):
            (folder / other).write_text("null" if other == name else content, encoding="utf-8")
        report = finalize_run_dir(folder)
        assert report[S.STATUS] == S.STATUS_ESCALATED, name
        assert S.REPORT_JSON_FILE in run_files(folder) and S.REPORT_MD_FILE in run_files(folder)


def test_list_typed_files_are_coerced(tmp_path):
    folder = make_run(tmp_path, [1, 2, 3], run_info=["x"])
    (folder / S.LEDGER_FILE).write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    report = finalize_run_dir(folder)
    assert report[S.STATUS] == S.STATUS_ESCALATED and report[S.INCIDENT_ID] == "run"
    assert "run info missing" in report[S.ESCALATION_REASON]


def test_a_missing_file_gives_an_escalated_report_naming_it(tmp_path):
    for missing, expected in ((S.LEDGER_FILE, "ledger.json is missing"), (S.CANDIDATE_FILE, "candidate.json is missing"),
                              (S.RUN_INFO_FILE, "run info missing")):
        folder = tmp_path / missing.split(".")[0]
        folder.mkdir()
        shutil.copy(LEDGERS / "live_container_fault.json", folder / S.LEDGER_FILE)
        (folder / S.CANDIDATE_FILE).write_text(json.dumps(good_candidate()), encoding="utf-8")
        (folder / S.RUN_INFO_FILE).write_text(json.dumps(RUN_INFO), encoding="utf-8")
        (folder / missing).unlink()
        report = finalize_run_dir(folder)
        assert report[S.STATUS] == S.STATUS_ESCALATED and expected in report[S.ESCALATION_REASON], missing
        assert (folder / S.REPORT_JSON_FILE).exists() and (folder / S.REPORT_MD_FILE).exists()


def test_missing_run_info_falls_back_to_the_folder_name_and_the_cli_exits_0(tmp_path, capsys):
    folder = make_run(tmp_path, good_candidate())
    (folder / S.RUN_INFO_FILE).unlink()
    assert main([str(folder)]) == 0
    report = json.loads((folder / S.REPORT_JSON_FILE).read_text(encoding="utf-8"))
    assert report[S.INCIDENT_ID] == "run" and "run info missing" in report[S.ESCALATION_REASON]
    assert "ESCALATED" in capsys.readouterr().out


def test_empty_folder_gives_an_escalated_report_naming_every_missing_file(tmp_path):
    folder = tmp_path / "inc-empty"
    folder.mkdir()
    report = finalize_run_dir(folder)
    reason = report[S.ESCALATION_REASON]
    assert report[S.INCIDENT_ID] == "inc-empty" and report[S.STATUS] == S.STATUS_ESCALATED
    assert "ledger.json is missing" in reason and "candidate.json is missing" in reason and "run info missing" in reason


def test_non_dict_inputs_are_coerced_in_finalize(tmp_path):
    for candidate, ledger, info in ((None, None, None), ([1], "x", 5), ("c", 7, [])):
        report = finalize(candidate, ledger, info, tmp_path / "o")
        assert report[S.STATUS] == S.STATUS_ESCALATED and list(report) == list(S.REPORT_FIELDS)


def test_string_alternatives_become_hypothesis_dicts(tmp_path):
    cand = good_candidate()
    cand["alternatives_considered"] = ["cart bug", {"hypothesis": "network", "why_rejected": "no errors"}, "  ", None]
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    assert report[S.ALTERNATIVES] == [{"hypothesis": "cart bug", "why_rejected": ""},
                                      {"hypothesis": "network", "why_rejected": "no errors"}]
    assert report[S.STATUS] == S.STATUS_DIAGNOSED
    assert "- cart bug: " in (tmp_path / S.REPORT_MD_FILE).read_text(encoding="utf-8")


def test_a_lone_string_alternative_counts_as_one(tmp_path):
    cand = good_candidate()
    cand["alternatives_considered"] = "cart bug"
    report = finalize(cand, load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, tmp_path)
    assert report[S.ALTERNATIVES] == [{"hypothesis": "cart bug", "why_rejected": ""}]


def test_odd_shapes_inside_the_candidate_do_not_crash(tmp_path):
    cand = {"component": ["x"], "cause": {"a": 1}, "stated_confidence": "high", "evidence": "none",
            "alternatives_considered": 5, "investigation_steps": "s", "limitations": 7}
    report = finalize(cand, [None, 3, {"id": None}], RUN_INFO, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED and report[S.CONFIDENCE] == 0.0
    assert report[S.STEPS] == ["s"] and report[S.LIMITATIONS] == []


def test_an_unexpected_error_gives_an_escalated_report_with_the_error_noted(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("kaboom")
    monkeypatch.setattr("oncall.report.validate_evidence", boom)
    report = finalize(good_candidate(), [], RUN_INFO, tmp_path)
    assert report[S.STATUS] == S.STATUS_ESCALATED and "RuntimeError: kaboom" in report[S.ESCALATION_REASON]
    assert report[S.INCIDENT_ID] == "inc-test-0001"
    assert json.loads((tmp_path / S.REPORT_JSON_FILE).read_text(encoding="utf-8")) == report


def test_nothing_is_written_when_the_output_cannot_be_completed(tmp_path, monkeypatch):
    out = tmp_path / "out"
    real = Path.write_text
    calls = []

    def flaky(self, *args, **kwargs):
        calls.append(self.name)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(self, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", flaky)
    try:
        finalize(good_candidate(), load_ledger(LEDGERS / "live_container_fault.json"), RUN_INFO, out)
    except OSError:
        pass
    assert run_files(out) == []


def test_nothing_is_written_when_rendering_fails_twice(tmp_path, monkeypatch):
    monkeypatch.setattr("oncall.report.render_markdown", lambda report: 1 / 0)
    out = tmp_path / "out"
    try:
        finalize(good_candidate(), [], RUN_INFO, out)
    except ZeroDivisionError:
        pass
    assert not out.exists()
