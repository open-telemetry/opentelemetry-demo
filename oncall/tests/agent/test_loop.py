import json
import re

import pytest

from oncall.agent.llm import LLMError, LLMReply
from oncall.agent.loop import investigate
from oncall.agent.runlog import RunLog
from oncall.tests.agent.stub_tools import HOT_SERVICE, STUB_SCHEMAS, STUB_TOOLS

ALERT = {
    "id": "a1",
    "ts": "2026-10-23T10:00:00Z",
    "service": None,
    "signal": "manual",
    "value": None,
    "threshold": None,
    "description": "error rate high",
    "source": "manual",
}
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def call(name: str, args: dict | None, i: int = 0, error: str | None = None) -> dict:
    c = {"id": f"c{i}", "name": name, "args": args}
    if error:
        c["error"] = error
    return c


class ScriptedLLM:
    """Each script step is a function of the messages so far, returning an LLMReply."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, tools):
        self.calls += 1
        step = self.script.pop(0) if self.script else self.script_last
        self.script_last = step
        return step(messages)


def reply(*calls) -> callable:
    return lambda messages: LLMReply(text="", tool_calls=list(calls), usage=USAGE)


def last_tool_result(messages) -> dict:
    return json.loads([m for m in messages if m["role"] == "tool"][-1]["content"])


@pytest.fixture
def runlog(tmp_path):
    return RunLog(run_id="test", runs_dir=str(tmp_path))


def run(llm, runlog, max_steps=12):
    return investigate(
        ALERT,
        tools=STUB_TOOLS,
        llm=llm,
        max_steps=max_steps,
        runlog=runlog,
        schemas=STUB_SCHEMAS,
    )


def test_dependent_tool_chain(runlog):
    def pick_hot_service(messages):
        summary = last_tool_result(messages)["summary"]
        service = re.search(r"by service: (\w+)=", summary).group(1)
        return LLMReply(
            "", [call("stub_search_traces", {"service": service}, 2)], USAGE
        )

    def logs_for_traced_service(messages):
        service = last_tool_result(messages)["query"]["service"]
        return LLMReply("", [call("stub_search_logs", {"service": service}, 3)], USAGE)

    llm = ScriptedLLM(
        [
            reply(call("stub_get_metrics", {}, 1)),
            pick_hot_service,
            logs_for_traced_service,
            reply(
                call("finish", {"summary": "cart errors [trace:abc123/span:GetCart]"})
            ),
        ]
    )
    result = run(llm, runlog)

    assert result["stopped"] == "finish"
    assert result["tools_used"] == [
        "stub_get_metrics",
        "stub_search_traces",
        "stub_search_logs",
    ]
    assert [e["args"] for e in runlog.events("tool_call")][1] == {
        "service": HOT_SERVICE
    }
    assert result["summary"] == "cart errors [trace:abc123/span:GetCart]"
    assert "trace:abc123/span:GetCart" in runlog.evidence_index()
    assert runlog.token_usage()["total_tokens"] == 4 * 15


def test_stops_at_max_steps(runlog):
    llm = ScriptedLLM([reply(call("stub_get_metrics", {}))])
    result = run(llm, runlog, max_steps=3)
    assert result["stopped"] == "max_steps"
    assert result["steps"] == 3
    assert llm.calls == 3 + 1  # three steps, then one forced-finish call
    assert runlog.events("finish")[0]["stopped"] == "max_steps"
    assert result["summary"].startswith("Investigation stopped (max_steps)")


def test_unknown_tool_reported_back(runlog):
    seen = {}

    def check_error(messages):
        seen["result"] = last_tool_result(messages)
        return LLMReply("", [call("finish", {"summary": "done"})], USAGE)

    llm = ScriptedLLM([reply(call("no_such_tool", {})), check_error])
    result = run(llm, runlog)
    assert result["stopped"] == "finish"
    assert seen["result"]["ok"] is False
    assert "unknown tool 'no_such_tool'" in seen["result"]["error"]


def test_bad_args_reported_back(runlog):
    llm = ScriptedLLM(
        [
            reply(call("stub_search_traces", {})),
            reply(call("stub_search_traces", None, error="arguments are not valid")),
        ]
    )
    result = run(llm, runlog)
    results = [e["result"] for e in runlog.events("tool_result")]
    assert "TypeError" in results[0]["error"]
    assert results[1]["error"] == "arguments are not valid"
    assert result["stopped"] == "error"


def test_two_consecutive_tool_errors_stop(runlog):
    llm = ScriptedLLM([reply(call("nope", {}))])
    result = run(llm, runlog)
    assert result["stopped"] == "error"
    assert result["steps"] == 2


def test_error_counter_resets_after_success(runlog):
    llm = ScriptedLLM(
        [
            reply(call("nope", {})),
            reply(call("stub_get_metrics", {})),
            reply(call("nope", {})),
            reply(call("finish", {"summary": "ok"})),
        ]
    )
    assert run(llm, runlog)["stopped"] == "finish"


def test_llm_error_stops_cleanly(runlog):
    def boom(messages):
        raise LLMError("HTTP 500")

    result = run(ScriptedLLM([boom]), runlog)
    assert result["stopped"] == "error"
    assert "HTTP 500" in result["summary"]
    assert runlog.events("error")[0]["where"] == "llm_call"


def test_text_only_reply_is_nudged_then_stops(runlog):
    def text(messages):
        return LLMReply("I think it is cart", [], USAGE)

    llm = ScriptedLLM([text])
    result = run(llm, runlog)
    assert result["stopped"] == "error"
    assert llm.calls == 2
