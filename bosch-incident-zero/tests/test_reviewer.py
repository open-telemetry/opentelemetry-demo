"""Reviewer pass: verdict parsing, deterministic confidence rules, evidence-only refs, no tools."""
from __future__ import annotations

import json

import pytest

from src.agent import reviewer as rv
from src.agent.agent import IncidentAgent
from src.agent.llm import LLMRateLimitError, LLMResponse, ScriptedSession
from tests.test_agent_loop import TRACE, good_diag, investigation_script, toolbox


@pytest.fixture
def transcript(tmp_path):
    queue = [ScriptedSession(investigation_script()), ScriptedSession([LLMResponse(text=json.dumps(good_diag()))])]
    t = IncidentAgent(toolbox(), lambda s, tools: queue.pop(0), output_dir=tmp_path).run("Errors on checkout")
    assert t.gate["final_confidence"] == "high" and not t.gate["escalate"]
    return t


def reviewer_factory(*replies):
    made = []

    def factory(system, tools):
        session = ScriptedSession([r if callable(r) else LLMResponse(text=r) for r in replies])
        made.append((system, list(tools), session))
        return session
    factory.made = made
    return factory


def reply(verdict, reasons=("x",), refs=(), alt=None):
    return json.dumps({"verdict": verdict, "reasons": list(reasons), "refs": list(refs),
                       "better_alternative": alt})


def test_reviewer_gets_no_tools_and_only_transcript_evidence(transcript):
    f = reviewer_factory(reply("upheld", []))
    rv.review(transcript, f)
    system, tools, session = f.made[0]
    assert tools == [] and "skeptical" in system
    prompt = session.received[0]["user_text"]
    assert "Errors on checkout" in prompt and TRACE in prompt and "payment" in prompt


def test_upheld_never_changes_confidence(transcript):
    result = rv.review(transcript, reviewer_factory(reply("upheld", [])))
    gate = rv.apply_review(transcript.gate, result)
    assert result["verdict"] == "upheld"
    assert gate["final_confidence"] == "high" and not gate["escalate"]
    assert gate["review"]["confidence_before"] == "high" == gate["review"]["confidence_after"]


def test_weakened_lowers_one_level(transcript):
    result = rv.review(transcript, reviewer_factory(reply("weakened", ["log quote is generic"])))
    gate = rv.apply_review(transcript.gate, result)
    assert gate["final_confidence"] == "medium" and not gate["escalate"]
    assert any("log quote is generic" in r for r in gate["reasons"])


def test_weakened_from_medium_reaches_low_and_escalates():
    gate = rv.apply_review({"final_confidence": "medium", "escalate": False},
                           {"verdict": "weakened", "reasons": ["one signal only"]})
    assert gate["final_confidence"] == "low" and gate["escalate"]


def test_refuted_caps_at_low_and_escalates(transcript):
    result = rv.review(transcript, reviewer_factory(
        reply("refuted", ["checkout calls never reached payment"], refs=[TRACE], alt="checkout")))
    gate = rv.apply_review(transcript.gate, result)
    assert gate["final_confidence"] == "low" and gate["escalate"]
    assert result["better_alternative"] == "checkout" and result["valid_refs"] == [TRACE]
    assert transcript.gate["final_confidence"] == "high"  # the input gate is not mutated


def test_invented_refs_are_dropped_and_listed(transcript):
    result = rv.review(transcript, reviewer_factory(
        reply("weakened", ["see trace"], refs=["f" * 32, "metric:payment:error_rate"])))
    assert result["valid_refs"] == ["metric:payment:error_rate"] and result["invalid_refs"] == ["f" * 32]
    assert "ignored refs" in rv.format_review(result)


def test_invalid_output_gets_one_retry(transcript):
    f = reviewer_factory("not json", reply("weakened", ["over-confident"]))
    result = rv.review(transcript, f)
    assert result["verdict"] == "weakened"
    assert "rejected" in f.made[0][2].received[1]["user_text"]


@pytest.mark.parametrize("bad", [
    json.dumps({"verdict": "maybe", "reasons": []}),
    json.dumps({"verdict": "refuted", "reasons": []}),
    json.dumps({"verdict": "weakened", "reasons": "a string"}),
])
def test_still_invalid_after_retry_is_unavailable_and_changes_nothing(transcript, bad):
    result = rv.review(transcript, reviewer_factory(bad, bad))
    gate = rv.apply_review(transcript.gate, result)
    assert result["verdict"] == "unavailable"
    assert gate["final_confidence"] == "high" and any("reviewer unavailable" in r for r in gate["reasons"])


def test_llm_failure_is_unavailable_not_a_crash(transcript):
    def quota(*_):
        raise LLMRateLimitError("daily quota exceeded")
    result = rv.review(transcript, reviewer_factory(quota))
    assert result["verdict"] == "unavailable" and "quota" in result["reasons"][0]


def test_no_diagnosis_is_not_sent_to_the_model():
    from src.agent.transcript import Transcript
    f = reviewer_factory(reply("upheld", []))
    result = rv.review(Transcript(incident_id="X", alert="a"), f)
    assert result["verdict"] == "unavailable" and f.made == []


def test_format_review_for_the_operator():
    text = rv.format_review({"verdict": "refuted", "reasons": ["caller blamed"], "better_alternative": "payment",
                             "confidence_before": "high", "confidence_after": "low", "invalid_refs": []})
    assert "REFUTED" in text and "high -> low" in text and "caller blamed" in text and "payment" in text
