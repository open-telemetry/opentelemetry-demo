import json

import pytest

from oncall.agent.diagnosis import escalate_unknown
from oncall.agent.loop import investigate_and_diagnose
from oncall.agent.runlog import RunLog
from oncall.main import _manual_alert
from oncall.models import make_result
from oncall.report.output import (
    build_report,
    fallback_report,
    finalise_report,
    repair,
    to_markdown,
    validate,
    write,
)

M_ID = "metric:error_rate:payment@2026-10-23T20:00:00+00:00"
T_ID = "trace:abc/span:Charge"
M_TEXT = "payment error_rate 0.4000 (baseline 0.0100, delta +0.3900)"


@pytest.fixture
def run(tmp_path):
    r = RunLog(run_id="r1", runs_dir=str(tmp_path))
    r.log("alert", alert=_manual_alert(None, "users report errors"))
    r.log("tool_call", step=1, name="get_metrics", args={"metric": "error_rate"})
    r.log(
        "tool_result",
        step=1,
        name="get_metrics",
        result=make_result(
            "get_metrics", {}, "s", [{"id": M_ID, "text": M_TEXT, "ts": "t1"}]
        ),
    )
    r.log(
        "tool_result",
        step=2,
        name="search_traces",
        result=make_result(
            "search_traces",
            {},
            "s",
            [{"id": T_ID, "text": "payment ERROR card declined", "ts": None}],
        ),
    )
    r.log("finish", stopped="finish", summary="payment fails", steps=2)
    return r


def _diagnosis(**over):
    d = {
        "component": "payment",
        "category": "app_error",
        "cause": "payment charge fails",
        "confidence": 0.9,
        "evidence_ids": [M_ID, T_ID],
        "affected_services": ["payment", "checkout"],
        "alternatives": [{"hypothesis": "network", "rejected_because": "no timeouts"}],
        "decision": "act",
        "reasoning": f"errors [{M_ID}]",
    }
    d.update(over)
    return d


def test_report_is_valid_and_copies_evidence_verbatim(run):
    alert = _manual_alert(None, "users report errors")
    report = build_report(alert, _diagnosis(), run)
    assert validate(report) == []
    index = run.evidence_index()
    for item in report["evidence"]:
        assert item["text"] == index[item["id"]]["text"]
    assert report["evidence"][0]["source"] == "get_metrics"
    assert [t["event"] for t in report["timeline"]][:2] == [
        "alert received",
        'tool get_metrics({"metric": "error_rate"})',
    ]


@pytest.mark.parametrize(
    "d",
    [
        _diagnosis(category="no_incident", decision="no_action", component=None),
        escalate_unknown("LLM unavailable"),
    ],
)
def test_every_decision_kind_is_valid(run, d):
    assert validate(build_report(_manual_alert(None, "x"), d, run)) == []


def test_repair_fixes_types_and_unknown_values(run):
    report = build_report(_manual_alert(None, "x"), _diagnosis(), run)
    report.update(confidence="high", decision="maybe", extra=1)
    report["root_cause"]["category"] = "bad"
    del report["timeline"]
    assert validate(report)
    fixed = repair(report)
    assert validate(fixed) == []
    assert (fixed["decision"], fixed["confidence"]) == ("escalate", 0.0)


def test_missing_diagnosis_falls_back_to_valid_escalate(run):
    report, notes = finalise_report(_manual_alert(None, "x"), None, run)
    assert validate(report) == []
    assert report["decision"] == "escalate"
    assert notes and notes[0].startswith("build failed")


def test_forced_llm_failure_still_writes_valid_report(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    run = RunLog(run_id="fail", runs_dir=str(tmp_path))
    alert = _manual_alert(None, "x")
    result = investigate_and_diagnose(alert, tools={}, runlog=run, schemas={})
    report, _ = finalise_report(alert, result["diagnosis"], run)
    json_path, md_path = write(report, tmp_path / "reports")
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert validate(saved) == []
    assert saved["decision"] == "escalate"
    assert md_path.read_text(encoding="utf-8").startswith("# Incident fail")


def test_write_refuses_invalid_report(run, tmp_path):
    with pytest.raises(ValueError):
        write({"incident_id": "x"}, tmp_path)


def test_fallback_and_markdown(run):
    report = fallback_report(_manual_alert("cart", "x"), run, "boom")
    assert validate(report) == []
    md = to_markdown(report)
    assert "## Evidence" in md and "report fallback: boom" in md


def test_report_lists_llm_models_in_first_use_order(run):
    for model in (
        "groq:openai/gpt-oss-120b",
        "groq:openai/gpt-oss-20b",
        "groq:openai/gpt-oss-120b",
    ):
        run.log("llm_call", step=1, model=model, usage={})
    report = build_report(_manual_alert(None, "x"), _diagnosis(), run)
    assert report["llm_models"] == [
        "groq:openai/gpt-oss-120b",
        "groq:openai/gpt-oss-20b",
    ]
    assert validate(report) == []
    assert "LLM: groq:openai/gpt-oss-120b, groq:openai/gpt-oss-20b" in to_markdown(
        report
    )
