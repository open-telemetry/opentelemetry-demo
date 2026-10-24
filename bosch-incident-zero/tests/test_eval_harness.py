"""Unit and regression tests for evaluation harness and scoring logic."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from src.agent.eval_harness import main, run_faultctl, score


def test_score_correct_diagnosis_passes():
    transcript = SimpleNamespace(
        diagnosis={"root_cause": {"service": "payment", "category": "errors_on_operation"}},
        gate={"escalate": False, "final_confidence": "high", "invalid_citations": 0},
        report_schema_valid=True,
        tool_calls=[1, 2, 3],
    )
    expected = {"service": "payment", "category": "errors_on_operation"}
    result = score(expected, transcript)

    assert result["outcome"] == "PASS"
    assert result["diagnosis_correct"] is True
    assert result["schema_valid"] is True
    assert result["citations_valid"] is True
    assert result["escalated"] is False
    assert result["service_match"] is True
    assert result["category_match"] is True
    assert result["predicted_service"] == "payment"
    assert result["predicted_category"] == "errors_on_operation"
    assert result["confidence"] == "high"


def test_score_incorrect_service_fails():
    transcript = SimpleNamespace(
        diagnosis={"root_cause": {"service": "checkout", "category": "errors_on_operation"}},
        gate={"escalate": False, "final_confidence": "medium", "invalid_citations": 0},
        report_schema_valid=True,
        tool_calls=[1, 2],
    )
    expected = {"service": "payment", "category": "errors_on_operation"}
    result = score(expected, transcript)

    assert result["outcome"] == "FAIL_DIAGNOSIS"
    assert result["diagnosis_correct"] is False
    assert result["service_match"] is False
    assert result["predicted_service"] == "checkout"


def test_score_schema_invalid_fails_even_if_diagnosis_matches():
    transcript = SimpleNamespace(
        diagnosis={"root_cause": {"service": "payment", "category": "errors_on_operation"}},
        gate={"escalate": False, "final_confidence": "high", "invalid_citations": 0},
        report_schema_valid=False,
        tool_calls=[1, 2],
    )
    expected = {"service": "payment", "category": "errors_on_operation"}
    result = score(expected, transcript)

    assert result["outcome"] == "FAIL_SCHEMA_INVALID"
    assert result["diagnosis_correct"] is True
    assert result["schema_valid"] is False


def test_score_invalid_citations_fails_even_if_diagnosis_matches():
    transcript = SimpleNamespace(
        diagnosis={"root_cause": {"service": "payment", "category": "errors_on_operation"}},
        gate={"escalate": False, "final_confidence": "high", "invalid_citations": 2},
        report_schema_valid=True,
        tool_calls=[1, 2],
    )
    expected = {"service": "payment", "category": "errors_on_operation"}
    result = score(expected, transcript)

    assert result["outcome"] == "FAIL_INVALID_CITATIONS"
    assert result["diagnosis_correct"] is True
    assert result["citations_valid"] is False
    assert result["invalid_citations"] == 2


def test_score_no_diagnosis_reported():
    transcript = SimpleNamespace(
        diagnosis=None,
        gate={"escalate": False, "final_confidence": "low", "invalid_citations": 0},
        report_schema_valid=False,
        tool_calls=[],
    )
    expected = {"service": "payment", "category": "errors_on_operation"}
    result = score(expected, transcript)

    assert result["outcome"] == "NO_DIAGNOSIS"
    assert result["diagnosis_correct"] is False


def test_score_escalated_diagnosis_marked_escalated():
    transcript = SimpleNamespace(
        diagnosis={"root_cause": {"service": "payment", "category": "errors_on_operation"}},
        gate={"escalate": True, "final_confidence": "low", "invalid_citations": 0},
        report_schema_valid=True,
        tool_calls=[1],
    )
    expected = {"service": "payment", "category": "errors_on_operation"}
    result = score(expected, transcript)

    assert result["outcome"] == "ESCALATED"
    assert result["escalated"] is True


def test_run_faultctl_missing_env_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FAULTCTL_CMD", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        run_faultctl(["inject", "test"])
    assert "FAULTCTL_CMD is not set" in str(exc_info.value)


def test_eval_harness_missing_incident_file_blocks(capsys: pytest.CaptureFixture):
    exit_code = main(["nonexistent_incidents_file.json"])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "BLOCKED: Incident definition file" in captured.err


def test_eval_harness_malformed_json_blocks(tmp_path: Path, capsys: pytest.CaptureFixture):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{malformed: json")
    exit_code = main([str(bad_json)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "BLOCKED: Failed to parse incident file" in captured.err


def test_eval_harness_non_list_root_blocks(tmp_path: Path, capsys: pytest.CaptureFixture):
    dict_json = tmp_path / "dict.json"
    dict_json.write_text('{"id": "incident-1"}')
    exit_code = main([str(dict_json)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "BLOCKED: Incident file root must be a JSON array" in captured.err


def test_eval_harness_empty_incident_list_blocks(tmp_path: Path, capsys: pytest.CaptureFixture):
    empty_json = tmp_path / "empty.json"
    empty_json.write_text("[]")
    exit_code = main([str(empty_json)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "BLOCKED: Incident file contains no incidents" in captured.err


def test_eval_harness_missing_required_keys_blocks(tmp_path: Path, capsys: pytest.CaptureFixture):
    inc_file = tmp_path / "missing_keys.json"
    inc_file.write_text('[{"id": "inc-01"}]')  # missing alert and inject
    exit_code = main([str(inc_file)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "BLOCKED: Incident 'inc-01' missing required keys" in captured.err


def test_eval_harness_only_filter_no_match_blocks(tmp_path: Path, capsys: pytest.CaptureFixture):
    inc_file = tmp_path / "incidents.json"
    inc_file.write_text('[{"id": "inc-01", "alert": "test", "inject": ["inject", "inc-01"]}]')
    exit_code = main([str(inc_file), "--only", "inc-99"])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "BLOCKED: --only filter matched zero incidents" in captured.err


def test_eval_harness_missing_faultctl_cmd_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    monkeypatch.delenv("FAULTCTL_CMD", raising=False)
    dummy_file = tmp_path / "incidents.json"
    dummy_file.write_text('[{"id": "inc-01", "alert": "test", "inject": ["inject", "inc-01"]}]')

    exit_code = main([str(dummy_file)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "BLOCKED: FAULTCTL_CMD is not set" in captured.err
