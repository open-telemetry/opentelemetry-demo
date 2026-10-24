"""Calibration report: accuracy per confidence level from harness results."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "calibration_report", Path(__file__).resolve().parents[1] / "scripts" / "calibration_report.py")
cr = importlib.util.module_from_spec(_SPEC)
sys.modules["calibration_report"] = cr
_SPEC.loader.exec_module(cr)


def row(conf, correct, outcome=None):
    return {"id": "x", "outcome": outcome or ("PASS" if correct else "FAIL"),
            "observed": {"confidence": conf}, "checks": {"diagnosis_correct": correct}}


ROWS = [row("high", True), row("high", True), row("high", False),
        row("medium", True), row("medium", False),
        row("low", True, "ESCALATED"), row("low", False, "ESCALATED"),
        row(None, False, "ERROR_MODEL"), row("high", False, "ERROR_INFRA")]


def test_accuracy_per_level_and_errors_counted_apart():
    rep = cr.calibrate(ROWS)
    assert rep["levels"]["high"] == {"cases": 3, "correct": 2, "escalated": 0, "passed": 2, "accuracy": 0.667}
    assert rep["levels"]["medium"]["accuracy"] == 0.5
    assert rep["levels"]["low"]["escalated"] == 2 and rep["levels"]["low"]["accuracy"] == 0.5
    assert rep["not_scored"] == 2 and rep["scored_cases"] == 7
    assert rep["overall_accuracy"] == round(4 / 7, 3) and rep["monotonic"] is True
    assert "unknown" not in rep["levels"]


def test_miscalibration_is_flagged():
    rep = cr.calibrate([row("high", False), row("medium", True)])
    assert rep["monotonic"] is False
    assert "miscalibrated" in cr.render(rep, [])


def test_falls_back_to_category_and_service_checks():
    old = {"outcome": "FAIL", "observed": {"confidence": "medium"},
           "checks": {"service_match": True, "category_match": False}}
    assert cr.calibrate([old])["levels"]["medium"]["correct"] == 0


def test_cli_reads_eval_dirs_and_jsonl_fallback(tmp_path, capsys):
    a = tmp_path / "eval-1"
    a.mkdir()
    (a / "results.json").write_text(json.dumps(ROWS[:3]))
    (a / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ROWS))  # ignored: results.json wins
    b = tmp_path / "eval-2"
    b.mkdir()
    (b / "results.jsonl").write_text(json.dumps(row("medium", True)) + "\n")      # interrupted run
    assert cr.main([str(tmp_path), "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["levels"]["high"]["cases"] == 3 and rep["levels"]["medium"]["cases"] == 1


def test_cli_text_output_and_small_sample_note(tmp_path, capsys):
    f = tmp_path / "results.json"
    f.write_text(json.dumps(ROWS))
    assert cr.main([str(f)]) == 0
    out = capsys.readouterr().out
    assert "high" in out and "67%" in out and "anecdotes" in out


def test_cli_without_results_exits_2(tmp_path, capsys):
    assert cr.main([str(tmp_path)]) == 2
    assert "no results.json" in capsys.readouterr().err


def test_bad_file_is_skipped(tmp_path, capsys):
    f = tmp_path / "results.json"
    f.write_text("{broken")
    assert cr.main([str(f)]) == 0
    assert "skipping" in capsys.readouterr().err
