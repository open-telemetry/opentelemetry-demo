import re
from pathlib import Path

import pytest

from oncall.agent import diagnosis, taxonomy
from oncall.agent.diagnosis import check, diagnose, escalate_unknown
from oncall.agent.llm import LLMError, LLMReply
from oncall.agent.loop import investigate_and_diagnose
from oncall.agent.runlog import RunLog
from oncall.models import make_result
from oncall.tests.agent.stub_tools import STUB_SCHEMAS, STUB_TOOLS
from oncall.tests.agent.test_loop import ALERT, USAGE, ScriptedLLM, call, reply

TRACE_ID = "trace:abc123/span:GetCart"
LOG_ID = "log:cart@2026-10-23T10:00:00Z"


def valid(**overrides) -> dict:
    d = {
        "component": "cart",
        "category": "app_error",
        "cause": "cart GetCart fails with connection refused to its cache.",
        "confidence": 0.8,
        "evidence_ids": [TRACE_ID, LOG_ID, TRACE_ID],
        "affected_services": ["cart", "checkout"],
        "alternatives": [
            {"hypothesis": "checkout bug", "rejected_because": "errors start in cart"}
        ],
        "decision": "act",
        "reasoning": f"Deepest ERROR span is in cart [{TRACE_ID}] [{LOG_ID}].",
    }
    d.update(overrides)
    return d


def submit(args) -> callable:
    return reply(call(diagnosis.SUBMIT, args))


@pytest.fixture
def run(tmp_path):
    rl = RunLog(run_id="t", runs_dir=str(tmp_path))
    traces = make_result(
        "search_traces",
        {"service": "cart"},
        "12 error traces",
        [{"id": TRACE_ID, "text": "GetCart ERROR", "ts": None}],
    )
    logs = make_result(
        "search_logs",
        {"service": "cart"},
        "connection refused x40",
        [{"id": LOG_ID, "text": "connection refused", "ts": None}],
    )
    rl.log("tool_result", step=1, name="search_traces", result=traces)
    rl.log("tool_result", step=2, name="search_logs", result=logs)
    rl.log("finish", stopped="finish", summary="cart errors", steps=3)
    return rl


def test_valid_diagnosis_returned(run):
    llm = ScriptedLLM([submit(valid())])
    d = diagnose(run, ALERT, llm)
    assert d["component"] == "cart"
    assert d["category"] == "app_error"
    assert d["decision"] == "act"
    assert d["evidence_ids"] == [TRACE_ID, LOG_ID]
    logged = run.events("decision")[-1]
    assert logged["valid"] is True
    assert logged["diagnosis"] == d


def test_invalid_then_valid_retries_once(run):
    seen = {}

    def second(messages):
        seen["retry"] = messages[-1]["content"]
        return LLMReply("", [call(diagnosis.SUBMIT, valid())], USAGE)

    llm = ScriptedLLM([submit(valid(category="cosmic_rays")), second])
    d = diagnose(run, ALERT, llm)
    assert llm.calls == 2
    assert d["category"] == "app_error"
    assert "category must be one of" in seen["retry"]


def test_invalid_twice_escalates_unknown(run):
    llm = ScriptedLLM([submit({"component": "cart"})])
    d = diagnose(run, ALERT, llm)
    assert llm.calls == diagnosis.MAX_ATTEMPTS
    assert d["decision"] == "escalate"
    assert d["category"] == "unknown"
    assert d["component"] is None
    assert "missing fields" in d["reasoning"]
    assert run.events("decision")[-1]["valid"] is False


def test_llm_error_escalates_unknown(run):
    def boom(messages):
        raise LLMError("HTTP 500")

    d = diagnose(run, {**ALERT, "service": "checkout"}, ScriptedLLM([boom]))
    assert d["decision"] == "escalate"
    assert d["category"] == "unknown"
    assert d["affected_services"] == ["checkout"]
    assert "HTTP 500" in d["reasoning"]


def test_text_reply_is_invalid(run):
    def text(messages):
        return LLMReply("it is cart", [], USAGE)

    d = diagnose(run, ALERT, ScriptedLLM([text]))
    assert d["category"] == "unknown"
    assert "must call submit_diagnosis" in d["reasoning"]


def test_bad_arguments_json_is_invalid(run):
    bad = reply(call(diagnosis.SUBMIT, None, error="arguments are not valid JSON"))
    d = diagnose(run, ALERT, ScriptedLLM([bad]))
    assert d["category"] == "unknown"


@pytest.mark.parametrize("client", taxonomy.CLIENT_SERVICES)
def test_client_never_component(run, client):
    d = diagnose(run, ALERT, ScriptedLLM([submit(valid(component=client))]))
    assert d["component"] is None
    assert d["decision"] == "escalate"
    assert client in d["affected_services"]
    assert d["reasoning"].startswith("[post-check:")


@pytest.mark.parametrize("confidence", [-0.1, 1.5, "high", True])
def test_bad_confidence_invalid(confidence):
    assert any("confidence" in p for p in check(valid(confidence=confidence)))


def test_check_accepts_valid_and_null_component():
    assert check(valid()) == []
    assert check(valid(component=None, decision="escalate")) == []


def test_check_rejects_wrong_types():
    problems = check(
        valid(component=3, evidence_ids="x", alternatives=[{"hypothesis": 1}])
    )
    assert len(problems) == 3
    assert check("nope") == ["the diagnosis must be a JSON object"]


def test_reasoning_truncated(run):
    long = valid(reasoning="x" * 5000)
    d = diagnose(run, ALERT, ScriptedLLM([submit(long)]))
    assert len(d["reasoning"]) == diagnosis.MAX_REASONING_CHARS


def test_prompt_includes_run_evidence_and_taxonomy(run):
    seen = {}

    def capture(messages):
        seen["prompt"] = messages[0]["content"]
        return LLMReply("", [call(diagnosis.SUBMIT, valid())], USAGE)

    diagnose(run, ALERT, ScriptedLLM([capture]))
    prompt = seen["prompt"]
    assert f"- {TRACE_ID}: GetCart ERROR" in prompt
    assert "search_logs" in prompt and "connection refused x40" in prompt
    assert "cart errors" in prompt
    for name in taxonomy.CATEGORIES:
        assert f"- {name}:" in prompt


def test_only_submit_tool_offered(run):
    seen = {}

    class Capture:
        def chat(self, messages, tools):
            seen["tools"] = tools
            return LLMReply("", [call(diagnosis.SUBMIT, valid())], USAGE)

    diagnose(run, ALERT, Capture())
    assert [t["name"] for t in seen["tools"]] == [diagnosis.SUBMIT]


def test_escalate_unknown_is_valid_payload():
    assert check(escalate_unknown("why")) == []


def test_investigate_and_diagnose(tmp_path):
    rl = RunLog(run_id="e2e", runs_dir=str(tmp_path))
    llm = ScriptedLLM(
        [
            reply(call("stub_search_traces", {"service": "cart"}, 1)),
            reply(call("finish", {"summary": "cart errors"}, 2)),
            submit(valid(evidence_ids=[TRACE_ID])),
        ]
    )
    result = investigate_and_diagnose(
        ALERT, tools=STUB_TOOLS, llm=llm, runlog=rl, schemas=STUB_SCHEMAS
    )
    assert result["stopped"] == "finish"
    assert result["diagnosis"]["component"] == "cart"
    assert TRACE_ID in rl.evidence_index()
    assert [e["event"] for e in rl.events()][-1] == "decision"


AGENT_DIR = Path(diagnosis.__file__).parent
# Flag wording (feature_flag / feature.flag / the flag service name, written
# "flag-?d" so this file passes CI's own grep) and answer-style mappings such
# as "scenario-01" or "scenario 3".
FORBIDDEN = re.compile(r"feature[_. ]?flag|flag-?d|scenario[- ]?\d", re.IGNORECASE)


@pytest.mark.parametrize("name", ["taxonomy.py", "prompts.py"])
def test_no_flag_or_scenario_text(name):
    text = (AGENT_DIR / name).read_text(encoding="utf-8")
    assert not FORBIDDEN.search(text)
