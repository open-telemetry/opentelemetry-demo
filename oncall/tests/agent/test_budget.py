import json

import pytest

from oncall.agent import loop
from oncall.agent.llm import LLMError, LLMReply
from oncall.agent.loop import (
    FINISH,
    compact,
    estimate_tokens,
    fallback_summary,
    investigate,
)
from oncall.agent.runlog import RunLog
from oncall.models import make_result
from oncall.tests.agent.test_loop import ALERT, USAGE, call

BIG_TEXT = "x" * 1400


def big_tool(service: str = "cart", n: int = 0):
    """A stub whose result is as large as the contract allows."""
    evidence = [
        {"id": f"log:{service}@{n}-{i}", "text": BIG_TEXT[:200], "ts": None}
        for i in range(20)
    ]
    return make_result("big_tool", {"service": service, "n": n}, BIG_TEXT, evidence)


TOOLS = {"big_tool": big_tool}
SCHEMAS = {
    "big_tool": {
        "name": "big_tool",
        "description": "big",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}, "n": {"type": "integer"}},
            "required": [],
        },
    }
}


class RecordingLLM:
    """Calls big_tool every turn; records prompt size and offered tools per call."""

    def __init__(self, finish_summary: str | None = "forced summary [log:cart@0-0]"):
        self.sizes, self.offered = [], []
        self.finish_summary = finish_summary

    def chat(self, messages, tools):
        self.sizes.append(estimate_tokens(messages, tools))
        self.offered.append([t["name"] for t in tools])
        if [t["name"] for t in tools] == [FINISH]:
            if self.finish_summary is None:
                return LLMReply("", [], USAGE)
            return LLMReply(
                "", [call(FINISH, {"summary": self.finish_summary}, 99)], USAGE
            )
        n = len(self.sizes)
        return LLMReply("", [call("big_tool", {"n": n}, n)], USAGE)


@pytest.fixture
def runlog(tmp_path):
    return RunLog(run_id="b", runs_dir=str(tmp_path))


@pytest.fixture
def budget(monkeypatch):
    monkeypatch.setenv("LLM_MAX_PROMPT_TOKENS", "6000")
    return 6000


def run(llm, runlog, max_steps=12):
    return investigate(
        ALERT, tools=TOOLS, llm=llm, max_steps=max_steps, runlog=runlog, schemas=SCHEMAS
    )


def test_history_stays_bounded_over_12_steps(runlog, budget):
    llm = RecordingLLM()
    result = run(llm, runlog)
    assert result["steps"] == 12
    assert len(llm.sizes) == 13
    assert max(llm.sizes) <= budget
    # Uncompacted, 12 results of this size would be about 12 x 2000 tokens.
    assert llm.sizes[-2] < 12 * 2000 / 2
    assert len(runlog.events("tool_result")) == 12
    assert all(len(e["result"]["evidence"]) == 20 for e in runlog.events("tool_result"))


def test_last_two_results_kept_in_full(runlog, budget):
    seen = {}

    class Capture(RecordingLLM):
        def chat(self, messages, tools):
            if len(self.sizes) == 4:
                seen["tool_msgs"] = [
                    json.loads(m["content"]) for m in messages if m["role"] == "tool"
                ]
            return super().chat(messages, tools)

    run(Capture(), runlog, max_steps=6)
    msgs = seen["tool_msgs"]
    assert len(msgs) == 4
    assert all("evidence" not in m and "evidence_ids" in m for m in msgs[:2])
    assert all(len(m["evidence"]) == 20 for m in msgs[2:])
    assert msgs[0]["evidence_ids"][0] == "log:cart@1-0"


def test_max_steps_run_returns_non_empty_summary(runlog, budget):
    llm = RecordingLLM()
    result = run(llm, runlog, max_steps=3)
    assert result["stopped"] == "max_steps"
    assert result["summary"] == "forced summary [log:cart@0-0]"
    assert llm.offered[-1] == [FINISH]
    assert all("big_tool" in o for o in llm.offered[:-1])


def test_fallback_summary_when_forced_finish_gives_nothing(runlog, budget):
    result = run(RecordingLLM(finish_summary=None), runlog, max_steps=3)
    s = result["summary"]
    assert s.startswith("Investigation stopped (max_steps)")
    assert "Tools called: big_tool, big_tool, big_tool" in s
    assert "[log:cart@1-0]" in s


def test_fallback_summary_when_forced_finish_errors(runlog, budget):
    class FailsAtFinish(RecordingLLM):
        def chat(self, messages, tools):
            if [t["name"] for t in tools] == [FINISH]:
                raise LLMError("HTTP 413")
            return super().chat(messages, tools)

    result = run(FailsAtFinish(), runlog, max_steps=2)
    assert result["summary"].startswith("Investigation stopped (max_steps)")
    assert runlog.events("error")[-1]["where"] == "forced_finish"


def test_tiny_budget_forces_finish_early(runlog, monkeypatch):
    monkeypatch.setenv("LLM_MAX_PROMPT_TOKENS", "1500")
    llm = RecordingLLM()
    result = run(llm, runlog)
    assert result["steps"] < 12
    assert runlog.events("budget")
    assert result["summary"]


def test_error_stop_summary_is_never_empty(runlog, budget):
    def boom(messages, tools):
        raise LLMError("HTTP 500")

    llm = RecordingLLM()
    llm.chat = boom
    result = run(llm, runlog)
    assert result["stopped"] == "error"
    assert "HTTP 500" in result["summary"]
    assert "No evidence was collected." in result["summary"]


def test_compact_levels():
    full = json.dumps(big_tool())
    msgs = [{"role": "tool", "content": full}] * 3
    compact(msgs, keep_full=1)
    assert "evidence" in json.loads(msgs[2]["content"])
    one = json.loads(msgs[0]["content"])
    assert set(one) == {"tool", "summary", "evidence_ids"}
    compact(msgs, keep_full=0, level=2)
    two = json.loads(msgs[2]["content"])
    assert len(two["summary"]) == loop.COMPACT_SUMMARY_CHARS
    assert len(two["evidence_ids"]) == loop.COMPACT_MAX_IDS
    compact(msgs, keep_full=0, level=3)
    assert json.loads(msgs[0]["content"]) == {
        "tool": "big_tool",
        "omitted": "see run log",
    }


def test_compact_keeps_error():
    err = json.dumps({"tool": "t", "summary": "", "evidence": [], "error": "boom"})
    msgs = [{"role": "tool", "content": err}]
    compact(msgs, keep_full=0)
    assert json.loads(msgs[0]["content"])["error"] == "boom"


def test_fallback_summary_empty_run(runlog):
    s = fallback_summary(runlog, "max_steps")
    assert "Tools called: none" in s and "No evidence was collected." in s


GROQ_413 = (
    '{"error":{"message":"Request too large for model on tokens per minute (TPM): '
    'Limit 8000, Requested 9512, please reduce your message size and try again."}}'
)


def test_shrunk_budget_uses_the_providers_overshoot():
    error = LLMError("HTTP 413", status=413, body=GROQ_413)
    assert loop.shrunk_budget(6000, error) == 6000 - 1512 - loop.SHRINK_MARGIN_TOKENS
    assert loop.shrunk_budget(6000, LLMError("HTTP 413", status=413)) == 4000


def test_413_compacts_and_retries_once(runlog, budget):
    class TooLargeOnce(RecordingLLM):
        failed = False

        def chat(self, messages, tools):
            if len(self.sizes) == 3 and not self.failed:
                self.failed = True
                raise LLMError("HTTP 413", status=413, body=GROQ_413)
            return super().chat(messages, tools)

    llm = TooLargeOnce()
    result = run(llm, runlog, max_steps=5)
    assert result["stopped"] == "max_steps"
    assert result["steps"] == 5
    event = runlog.events("budget")[0]
    assert event["reason"] == "413" and event["new_budget"] < 6000
    assert max(llm.sizes[3:]) <= event["new_budget"]


def test_second_413_stops_with_a_summary(runlog, budget):
    class AlwaysTooLarge(RecordingLLM):
        def chat(self, messages, tools):
            if len(self.sizes) >= 2:
                self.sizes.append(0)
                raise LLMError("HTTP 413", status=413, body=GROQ_413)
            return super().chat(messages, tools)

    result = run(AlwaysTooLarge(), runlog)
    assert result["stopped"] == "error"
    assert "413" in result["summary"]
    assert "Tools called: big_tool" in result["summary"]
