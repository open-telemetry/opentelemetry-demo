"""The investigation loop, driven by a scripted fake LLM and stub tools. No network, no cost."""
import copy
import dataclasses
import functools
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from oncall import toolbox
from oncall.investigate import main, symptom_summary
from oncall.llm import Reply, ToolCall
from oncall.loop import LoopConfig, SUBMIT, parse_submission, run_investigation
from tests.test_leak import leaks
from tests.test_toolbox import FIXTURES, ledger_from
from tools.result import ToolResult, backend_error

GOOD_DIAGNOSIS = {
    "component": "svc-b",
    "cause": "svc-b is down.",
    "stated_confidence": 0.8,
    "evidence": [{"ledger_id": "C1", "kind": "container", "claim": "svc-b is not running", "quote": "svc-b", "value": "exited"}],
    "alternatives_considered": [{"hypothesis": "svc-a is the cause", "why_rejected": "it only reports the symptom"}],
    "limitations": ["no logs checked"],
}


class ScriptedLLM:
    """Returns the prepared replies in order and records everything it was sent."""
    api_key = "sk-test-secret"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, messages, tools=None, max_tokens=1024):
        self.calls.append({"system": system, "messages": copy.deepcopy(messages), "tools": tools, "max_tokens": max_tokens})
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


_ids = iter(range(1, 10_000))


def call(name, **arguments):
    return ToolCall(f"call_{next(_ids)}", name, arguments)


def say(*calls, text="", usage=(1000, 50), stop=None):
    return Reply(text, list(calls), {"input_tokens": usage[0], "output_tokens": usage[1]}, stop)


def submit(**overrides):
    return call(SUBMIT, **{**GOOD_DIAGNOSIS, **overrides})


def ok(tool, **items):
    row = {"name": "svc-b", "status": "exited", "health": "none", "restart_count": 0, "exit_code": 1, "oom_killed": False}
    return ToolResult(tool, "data", [f"{tool} q"], {"at": "t"}, items=[row], total_items=1,
                      extra={"summary": {"total": 2, "running": 1, "not_running": ["svc-b"], "unhealthy": [], "restarted": [], "oom_killed": []}})


def stubs(**by_tool):
    """Replace tool functions with stubs that keep the real signature. Returns (tools, calls_seen)."""
    seen = []
    tools = dict(toolbox.TOOLS)
    for name in toolbox.TOOLS:
        result = by_tool.get(name)

        def make(original, result=result):
            @functools.wraps(original.fn)
            def fn(**kwargs):
                seen.append((original.name, kwargs))
                if isinstance(result, Exception):
                    raise result
                return result() if callable(result) else (result or ToolResult(original.name, "no_data", ["q"], {}))
            return fn

        tools[name] = dataclasses.replace(toolbox.TOOLS[name], fn=make(toolbox.TOOLS[name]))
    return tools, seen


def tool_messages(llm_call):
    return [m for m in llm_call["messages"] if m["role"] == "tool"]


def test_loop_calls_tools_in_the_scripted_order_and_nothing_is_preloaded():
    tools, seen = stubs(container_health=ok("container_health"))
    llm = ScriptedLLM([
        say(call("container_health"), text="Checking containers first."),
        say(call("query_metrics", window_minutes=5)),
        say(call("query_traces", service="svc-a")),
        say(submit()),
    ])
    run = run_investigation(llm, "things are slow", tools=tools)

    assert [name for name, _ in seen] == ["container_health", "query_metrics", "query_traces"]
    assert seen[1][1] == {"window_minutes": 5, "top_n": 6}  # defaults are filled in and recorded
    assert [s["ledger_id"] for s in run.candidate["investigation_steps"]] == ["C1", "M1", "T1"]
    assert run.candidate["investigation_steps"][0]["why"] == "Checking containers first."
    assert [e.arguments for e in run.ledger.list()][1] == {"window_minutes": 5, "top_n": 6}

    first = llm.calls[0]
    assert first["messages"] == [{"role": "user", "content": "Symptom report: things are slow"}]
    assert [t.name for t in first["tools"]] == [*toolbox.TOOLS, SUBMIT]
    assert first["max_tokens"] == LoopConfig().max_tokens
    # the model's second turn sees the compact view of C1, whose id it can cite
    view = json.loads(tool_messages(llm.calls[1])[0]["content"])
    assert view["id"] == "C1" and view["abnormal"][0]["name"] == "svc-b"

    c = run.candidate
    assert (c["component"], c["stated_confidence"]) == ("svc-b", 0.8)
    assert c["evidence"][0] == GOOD_DIAGNOSIS["evidence"][0]
    assert list(c) == ["component", "cause", "stated_confidence", "evidence", "alternatives_considered", "investigation_steps", "limitations"]
    assert run.run_info["stop_reason"] == "submitted" and not run.run_info["budget_exhausted"]


def test_run_info_is_produced_by_the_run():
    run = run_investigation(ScriptedLLM([say(submit(), usage=(700, 80))]), "slow", tools=stubs()[0])
    info = run.run_info
    assert re.fullmatch(r"inc-\d{8}-\d{6}-[0-9a-f]{4}", info["incident_id"])
    assert datetime.fromisoformat(info["started_at"]).tzinfo is not None
    assert (info["trigger"], info["steps_used"], info["step_budget"]) == ("slow", 0, 12)
    assert (info["budget_exhausted"], info["llm_error"], info["tokens_used"]) == (False, None, 780)
    json.dumps(info)
    json.dumps(run.candidate)


def test_two_runs_get_different_incident_ids():
    a = run_investigation(ScriptedLLM([say(submit())]), "x", tools=stubs()[0]).run_info["incident_id"]
    b = run_investigation(ScriptedLLM([say(submit())]), "x", tools=stubs()[0]).run_info["incident_id"]
    assert a != b


def test_defaults_are_the_tuned_budgets():
    config = LoopConfig()
    assert (config.token_budget, config.step_budget, config.reserve_fraction) == (200000, 12, 0.85)


def test_with_one_step_left_the_model_is_told_to_conclude_and_the_conclusion_carries_evidence():
    tools, seen = stubs(container_health=ok("container_health"))
    llm = ScriptedLLM([say(call("container_health")), say(call("query_logs", window_minutes=5)), say(submit())])
    run = run_investigation(llm, "x", LoopConfig(step_budget=3), tools)
    assert len(seen) == 2 and run.run_info["steps_used"] == 2  # the last step is held back
    assert run.run_info["budget_exhausted"] and run.run_info["stop_reason"] == "step_budget"
    assert run.candidate["evidence"] == GOOD_DIAGNOSIS["evidence"] and run.candidate["stated_confidence"] == 0.8
    assert any("cut short" in n for n in run.candidate["limitations"])
    # nothing is said before the last step is reached, then the reserve message rides on the latest tool result
    assert all("budget is nearly used up" not in m["content"] for m in tool_messages(llm.calls[1]))
    reserve = tool_messages(llm.calls[2])[-1]["content"]
    assert "nearly used up" in reserve and "only evidence you have already seen" in reserve and "submit_diagnosis" in reserve
    assert "about 2 tool calls" in llm.calls[0]["system"]


def test_at_85_percent_of_the_token_budget_the_model_must_conclude_with_evidence():
    config = LoopConfig(token_budget=10000, step_budget=30, max_tokens=100)
    replies = [say(call("query_logs", window_minutes=m), usage=(500, 50)) for m in range(1, 17)] + [say(submit())]
    llm = ScriptedLLM(replies)
    run = run_investigation(llm, "x", config, stubs()[0])
    assert run.run_info["stop_reason"] == "token_budget" and run.run_info["budget_exhausted"]
    assert len(llm.calls) == 17 and run.run_info["steps_used"] == 16
    assert 16 * 550 >= 0.85 * 10000 > 15 * 550  # 85% is crossed by the 16th call, not the 15th
    assert "nearly used up" not in tool_messages(llm.calls[15])[-1]["content"]  # 15 calls: still under 85%
    assert "nearly used up" in tool_messages(llm.calls[16])[-1]["content"]
    assert run.candidate["evidence"] and run.candidate["component"] == "svc-b"


def test_if_the_model_still_does_not_submit_after_the_reserve_message_the_candidate_is_unknown():
    llm = ScriptedLLM([say(call("query_logs", window_minutes=5)), say(text="still thinking"), say(text="still thinking")])
    run = run_investigation(llm, "x", LoopConfig(step_budget=2), stubs()[0])
    assert (run.candidate["component"], run.candidate["stated_confidence"], run.candidate["evidence"]) == ("unknown", 0.0, [])
    assert run.run_info["budget_exhausted"] and run.run_info["llm_error"]


def test_after_the_step_budget_more_tool_calls_are_not_run_and_the_candidate_is_partial_not_invented():
    tools, seen = stubs()
    llm = ScriptedLLM([say(call("query_logs", window_minutes=5)), say(call("query_logs", window_minutes=6)),
                       say(call("query_logs", window_minutes=7)), say(call("query_logs", window_minutes=8))])
    run = run_investigation(llm, "x", LoopConfig(step_budget=1), tools)
    assert len(seen) == 1 and len(llm.calls) == 3
    c = run.candidate
    assert (c["component"], c["stated_confidence"], c["evidence"]) == ("unknown", 0.0, [])
    assert run.run_info["budget_exhausted"] and "did not submit" in run.run_info["llm_error"]
    assert len(c["investigation_steps"]) == 1


def test_token_budget_that_cannot_fit_another_call_ends_the_run_without_calling_again():
    llm = ScriptedLLM([say(call("query_logs"), usage=(30000, 100)), say(submit())])
    run = run_investigation(llm, "x", LoopConfig(token_budget=60000), stubs()[0])
    assert len(llm.calls) == 1
    assert run.run_info["budget_exhausted"] and run.run_info["stop_reason"] == "token_budget"
    assert run.run_info["tokens_used"] == 30100
    assert run.candidate["component"] == "unknown" and run.candidate["stated_confidence"] == 0.0


def test_token_budget_leaves_room_for_the_final_answer():
    llm = ScriptedLLM([say(call("query_logs"), usage=(5000, 100)), say(submit(stated_confidence=0.3), usage=(5300, 200))])
    run = run_investigation(llm, "x", LoopConfig(token_budget=12000), stubs()[0])
    assert len(llm.calls) == 2
    assert run.run_info["budget_exhausted"] and run.run_info["tokens_used"] == 10600
    assert run.candidate["stated_confidence"] == 0.3


def test_repeated_identical_call_stops_the_investigation():
    tools, seen = stubs()
    llm = ScriptedLLM([say(call("query_metrics", window_minutes=5)),
                       say(call("query_metrics", window_minutes=5, top_n=6)),  # identical once defaults are applied
                       say(submit())])
    run = run_investigation(llm, "x", tools=tools)
    assert len(seen) == 1
    assert run.run_info["stop_reason"] == "repeated_call" and not run.run_info["budget_exhausted"]
    second = run.candidate["investigation_steps"][1]
    assert second["finding"] == "repeat of M1; not run" and second["ledger_id"] is None
    assert len(run.ledger.list()) == 1
    assert any("identical tool call" in n for n in run.candidate["limitations"])


NO_EVIDENCE = {"evidence": []}


def test_empty_evidence_is_sent_back_once_and_the_retry_is_counted():
    llm = ScriptedLLM([say(submit(**NO_EVIDENCE), usage=(2000, 100)), say(submit(), usage=(2200, 300))])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert len(llm.calls) == 2
    ask = tool_messages(llm.calls[1])[0]["content"]
    assert "no evidence items" in ask and "copied exactly" in ask
    assert run.candidate["evidence"] == GOOD_DIAGNOSIS["evidence"] and run.run_info["tokens_used"] == 4600
    assert run.candidate["limitations"] == GOOD_DIAGNOSIS["limitations"] and run.run_info["llm_error"] is None


def test_if_the_retry_is_still_empty_the_candidate_is_kept_with_a_note():
    llm = ScriptedLLM([say(submit(**NO_EVIDENCE)), say(submit(**NO_EVIDENCE, stated_confidence=0.4)), say(submit())])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert len(llm.calls) == 2  # asked once, never a second time
    assert (run.candidate["component"], run.candidate["stated_confidence"], run.candidate["evidence"]) == ("svc-b", 0.4, [])
    assert any("no evidence, even after one retry" in n for n in run.candidate["limitations"])


def test_no_retry_when_evidence_is_present_or_the_component_is_unknown():
    with_evidence = ScriptedLLM([say(submit())])
    run_investigation(with_evidence, "x", tools=stubs()[0])
    assert len(with_evidence.calls) == 1
    for component in ("unknown", "Unknown "):
        llm = ScriptedLLM([say(submit(component=component, stated_confidence=0.1, **NO_EVIDENCE))])
        run = run_investigation(llm, "x", tools=stubs()[0])
        assert len(llm.calls) == 1 and run.candidate["limitations"] == GOOD_DIAGNOSIS["limitations"]


def test_a_malformed_retry_falls_back_to_the_first_submission_not_to_unknown():
    llm = ScriptedLLM([say(submit(**NO_EVIDENCE)), say(submit(stated_confidence=85)), say(submit(stated_confidence=85))])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert run.candidate["component"] == "svc-b" and run.candidate["stated_confidence"] == 0.8
    assert any("retry did not produce a valid answer" in n for n in run.candidate["limitations"])
    assert "malformed" in run.run_info["llm_error"]


def test_the_retry_also_works_inside_the_forced_conclusion():
    llm = ScriptedLLM([say(call("query_logs", window_minutes=5)), say(submit(**NO_EVIDENCE)), say(submit())])
    run = run_investigation(llm, "x", LoopConfig(step_budget=2), stubs()[0])
    assert len(llm.calls) == 3 and run.candidate["evidence"] and run.run_info["budget_exhausted"]


def test_a_window_above_30_is_clamped_and_the_clamp_is_recorded_everywhere():
    tools, seen = stubs()
    llm = ScriptedLLM([say(call("query_logs", window_minutes=90)), say(call("query_traces")), say(call("query_metrics")), say(submit())])
    run = run_investigation(llm, "x", tools=tools)
    assert seen[0] == ("query_logs", {"window_minutes": 30, "limit": 6})
    assert [kw["window_minutes"] for _, kw in seen] == [30, 10, 5]  # defaults: logs and traces 10, metrics 5
    step = run.candidate["investigation_steps"][0]
    assert step["arguments"]["window_minutes"] == 30 and step["clamped"] == {"window_minutes": {"requested": 90, "used": 30}}
    assert "clamped to 30" in step["finding"] and "clamped" not in run.candidate["investigation_steps"][1]
    assert run.ledger.get("L1").arguments["window_minutes"] == 30  # what actually ran
    shown = tool_messages(llm.calls[1])[0]["content"]
    assert json.loads(shown)["clamped"] == {"window_minutes": {"requested": 90, "used": 30}}


def test_budgets_are_unchanged_by_the_hardening():
    assert (LoopConfig().token_budget, LoopConfig().step_budget, LoopConfig().reserve_fraction, LoopConfig().max_tokens) == (200000, 12, 0.85, 1200)


def test_unknown_tool_name_is_recorded_and_the_loop_carries_on():
    llm = ScriptedLLM([say(call("restart_service", target="x")), say(submit())])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert "restart_service" in run.run_info["llm_error"]
    assert run.candidate["investigation_steps"][0]["finding"] == "unknown tool; not run"
    assert run.ledger.list() == [] and run.candidate["component"] == "svc-b"
    assert "unknown tool" in tool_messages(llm.calls[1])[0]["content"]


def test_malformed_final_answer_gets_one_retry():
    llm = ScriptedLLM([say(submit(stated_confidence=85)), say(submit())])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert "rejected" in tool_messages(llm.calls[1])[0]["content"] and "stated_confidence" in tool_messages(llm.calls[1])[0]["content"]
    assert run.candidate["component"] == "svc-b" and run.run_info["llm_error"] is None


def test_malformed_twice_gives_a_partial_candidate_and_records_the_error():
    bad_kind = [{"ledger_id": "C1", "kind": "vibes", "claim": "c", "quote": "q"}]
    llm = ScriptedLLM([say(call(SUBMIT, component="x")), say(submit(evidence=bad_kind))])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert "malformed" in run.run_info["llm_error"] and run.run_info["stop_reason"] == "malformed_submission"
    assert (run.candidate["component"], run.candidate["stated_confidence"], run.candidate["evidence"]) == ("unknown", 0.0, [])


@pytest.mark.parametrize("change", [
    {"component": ""}, {"cause": None}, {"stated_confidence": True}, {"stated_confidence": -0.1}, {"stated_confidence": "0.5"},
    {"evidence": "C1"}, {"evidence": [{"ledger_id": "C1", "kind": "log", "claim": "c"}]},
    {"evidence": [{"ledger_id": "C1", "kind": "log", "claim": "c", "quote": "q", "value": 3}]},
    {"alternatives_considered": [{"hypothesis": "h"}]}, {"limitations": "none"},
])
def test_parse_submission_rejects_bad_shapes(change):
    from oncall.loop import DiagnosisError
    with pytest.raises(DiagnosisError):
        parse_submission({**GOOD_DIAGNOSIS, **change})


def test_parse_submission_keeps_quotes_exactly_as_sent():
    quote = '  "Payment request failed."\tx  '
    evidence = [{"ledger_id": "L1", "kind": "log", "claim": "c", "quote": quote}]
    assert parse_submission({**GOOD_DIAGNOSIS, "evidence": evidence})["evidence"][0] == {**evidence[0], "value": None}
    assert parse_submission({"component": "unknown", "cause": "no idea", "stated_confidence": 0})["evidence"] == []


def test_backend_error_result_is_shown_as_an_error_and_recorded_as_a_limitation():
    tools, _ = stubs(container_health=backend_error("container_health", ["docker ps"], {"at": "t"}, "docker ps failed: daemon down"))
    llm = ScriptedLLM([say(call("container_health")), say(submit(component="unknown", stated_confidence=0.1, evidence=[]))])
    run = run_investigation(llm, "x", tools=tools)
    view = json.loads(tool_messages(llm.calls[1])[0]["content"])
    assert view["state"] == "backend_error" and "daemon down" in view["error"] and "abnormal" not in view
    assert run.ledger.get("C1").result["state"] == "backend_error"
    assert "backend_error: docker ps failed: daemon down" in " ".join(run.candidate["limitations"])
    assert run.candidate["investigation_steps"][0]["finding"].startswith("C1: backend_error")


def test_a_tool_that_crashes_becomes_a_backend_error_not_a_dead_run():
    tools, _ = stubs(query_logs=RuntimeError("socket exploded"))
    run = run_investigation(ScriptedLLM([say(call("query_logs")), say(submit())]), "x", tools=tools)
    assert run.ledger.get("L1").result["state"] == "backend_error"
    assert "RuntimeError: socket exploded" in run.ledger.get("L1").result["error"]


def test_bad_arguments_are_sent_back_to_the_model_and_leave_no_ledger_entry():
    tools, seen = stubs(query_traces=ValueError("limit must be between 1 and 10"))
    llm = ScriptedLLM([say(call("query_traces", mode="bogus")),
                       say(call("query_traces", limit=99)),  # reaches the tool, which rejects the range
                       say(call("query_logs", nonsense=1)),
                       say(submit())])
    run = run_investigation(llm, "x", tools=tools)
    assert run.ledger.list() == [] and [n for n, _ in seen] == ["query_traces"]
    assert [s["finding"].startswith("rejected arguments") for s in run.candidate["investigation_steps"]] == [True] * 3
    assert "error:" in tool_messages(llm.calls[1])[0]["content"]
    assert run.run_info["steps_used"] == 3


def test_llm_timeout_keeps_partial_findings_and_never_prints_the_key():
    llm = ScriptedLLM([say(call("container_health")), TimeoutError("request timed out sk-test-secret")])
    tools, _ = stubs(container_health=ok("container_health"))
    run = run_investigation(llm, "x", tools=tools)
    assert run.run_info["llm_error"].startswith("TimeoutError: request timed out") and "sk-test-secret" not in json.dumps(run.run_info)
    assert run.run_info["stop_reason"] == "llm_error" and run.run_info["tokens_used"] == 1050
    assert run.candidate["component"] == "unknown" and run.candidate["stated_confidence"] == 0.0
    assert [s["ledger_id"] for s in run.candidate["investigation_steps"]] == ["C1"]
    assert "sk-test-secret" not in json.dumps(run.candidate)


def test_text_only_replies_are_nudged_once_then_recorded():
    llm = ScriptedLLM([say(text="I think it is the database."), say(text="Really, the database.")])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert len(llm.calls) == 2 and "without calling submit_diagnosis" in run.run_info["llm_error"]
    assert run.candidate["component"] == "unknown"
    assert run_investigation(ScriptedLLM([say(text="hmm"), say(submit())]), "x", tools=stubs()[0]).candidate["component"] == "svc-b"


def test_calls_in_one_turn_are_all_answered_and_a_submit_cancels_the_rest():
    tools, seen = stubs()
    llm = ScriptedLLM([say(call("query_logs"), call("deploy_history")), say(call("query_logs", window_minutes=9), submit())])
    run = run_investigation(llm, "x", tools=tools)
    assert [n for n, _ in seen] == ["query_logs", "deploy_history", ] and len(tool_messages(llm.calls[1])) == 2
    assert run.candidate["component"] == "svc-b" and len(run.ledger.list()) == 2


def test_the_model_is_only_ever_sent_generic_text_and_no_flag_data():
    """Replay recorded live ledgers as tool results and scan everything that is sent to the model."""
    for path in FIXTURES:
        recorded = {e.tool: e.result for e in ledger_from(path).list()}
        tools, _ = stubs(**{tool: ToolResult(**result) for tool, result in recorded.items()})
        llm = ScriptedLLM([say(*(call(t) for t in recorded)), say(submit(component="unknown", evidence=[]))])
        run_investigation(llm, "x", tools=tools)
        sent = json.dumps([{k: v for k, v in c.items() if k != "tools"} for c in llm.calls], default=str)
        assert leaks(sent) == [], path.name


# --- the command line and the symptom summary ---------------------------------------------

def test_symptom_summary_cites_only_ledger_ids():
    for path in FIXTURES:
        ledger = ledger_from(path)
        lines = symptom_summary(ledger)
        text = "\n".join(lines)
        cited = set(re.findall(r"\b([CMTLD]\d+)\b", text))
        assert cited and cited <= {e.id for e in ledger.list()}, path.name
        assert leaks(text) == []


def test_symptom_summary_says_when_evidence_is_missing():
    from tools.ledger import Ledger
    ledger = Ledger()
    ledger.add("query_logs", {}, backend_error("query_logs", ["q"], {}, "OpenSearch unreachable"))
    text = "\n".join(symptom_summary(ledger))
    assert "missing evidence, not a healthy signal" in text and "L1 query_logs: backend_error" in text
    assert symptom_summary(Ledger()) == ["No tool results were collected."]


def test_investigate_prints_steps_summary_and_tokens_and_saves_the_run(tmp_path, capsys):
    tools, _ = stubs(container_health=ok("container_health"))
    llm = ScriptedLLM([say(call("container_health"), text="Look at containers."), say(submit(), usage=(1200, 90))])
    import oncall.investigate as investigate
    original = investigate.run_investigation
    investigate.run_investigation = lambda llm_, symptom, config: original(llm_, symptom, config, tools)
    try:
        assert main(["--summary", "--symptom", "checkout is slow"], llm=llm, runs_dir=tmp_path) == 0
    finally:
        investigate.run_investigation = original
    out = capsys.readouterr().out
    assert "INVESTIGATION STEPS" in out and "container_health()" in out and "-> C1:" in out
    assert "SYMPTOM SUMMARY" in out and "C1: 1 of 2 containers running" in out
    assert "tokens used: 2340 of 200000" in out and "DIAGNOSIS CANDIDATE (not validated)" in out
    (folder,) = list(tmp_path.iterdir())
    assert sorted(p.name for p in folder.iterdir()) == ["candidate.json", "ledger.json", "run_info.json"]
    info = json.loads((folder / "run_info.json").read_text())
    assert info["trigger"] == "checkout is slow" and info["incident_id"] == folder.name
    assert json.loads((folder / "candidate.json").read_text())["component"] == "svc-b"
    assert json.loads((folder / "ledger.json").read_text())[0]["id"] == "C1"


def test_investigate_without_a_key_explains_and_exits(tmp_path, capsys, monkeypatch):
    import oncall.investigate as investigate
    from oncall.llm import LLMNotConfigured

    def no_key():
        raise LLMNotConfigured("no key configured")
    monkeypatch.setattr(investigate, "make_llm", no_key)
    assert main([], runs_dir=tmp_path) == 2
    assert "no key configured" in capsys.readouterr().err and list(tmp_path.iterdir()) == []


def test_llm_adapter_reports_usage_and_marks_prompt_cache_points():
    from oncall.llm import AnthropicProvider, ToolSpec

    class Usage:
        input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens = 100, 20, 300, 4000

    class Block:
        type, text = "text", "hi"

    class Client:
        sent = None

        class messages:
            @staticmethod
            def create(**kwargs):
                Client.sent = kwargs
                return type("R", (), {"content": [Block()], "usage": Usage(), "stop_reason": "max_tokens"})()

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.client, provider.model = Client(), "m"
    specs = [ToolSpec("a", "d", {"type": "object"}), ToolSpec("b", "d", {"type": "object"})]
    reply = provider.complete("be careful", [{"role": "user", "content": "go"}], specs, 50)
    assert reply.usage == {"input_tokens": 4400, "output_tokens": 20} and reply.stop_reason == "max_tokens"
    sent = Client.sent
    assert sent["system"] == [{"type": "text", "text": "be careful", "cache_control": {"type": "ephemeral"}}]
    assert "cache_control" not in sent["tools"][0] and sent["tools"][1]["cache_control"] == {"type": "ephemeral"}


# --- truncated final answers ----------------------------------------------------------------

def truncated(**missing):
    """A submission as the API returns it when the reply hit max_tokens: later fields never arrived."""
    cut = {k: v for k, v in GOOD_DIAGNOSIS.items() if k in ("component", "stated_confidence", "cause")}
    return call(SUBMIT, **{k: v for k, v in cut.items() if k not in missing})


def test_schema_puts_the_short_required_fields_first_and_the_long_lists_last():
    from oncall.loop import SUBMIT_SPEC
    assert list(SUBMIT_SPEC.parameters["properties"]) == [
        "component", "stated_confidence", "cause", "evidence", "alternatives_considered", "limitations"]
    assert SUBMIT_SPEC.parameters["required"] == ["component", "stated_confidence", "cause", "evidence"]


def test_prompt_asks_for_a_short_submission():
    from oncall.prompts import system_prompt
    text = system_prompt(11)
    assert "at most 5 evidence items" in text and "under 200 characters" in text and "at most 3 alternatives_considered" in text


def test_a_cut_off_submission_is_saved_called_cut_off_and_retried_with_a_shorter_message():
    raw = {"component": "svc-b", "cause": "svc-b is down.", "evidence": GOOD_DIAGNOSIS["evidence"]}  # stated_confidence never arrived
    llm = ScriptedLLM([say(call(SUBMIT, **raw), usage=(2000, 1200), stop="max_tokens"), say(submit(), usage=(2300, 400), stop="tool_use")])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert len(llm.calls) == 2 and run.candidate["component"] == "svc-b" and run.run_info["llm_error"] is None
    ask = tool_messages(llm.calls[1])[0]["content"]
    assert "cut off" in ask and "SHORTER" in ask and "stated_confidence" in ask
    assert "at most 3 evidence items" in ask and "under 100 characters" in ask
    (saved,) = run.rejected
    assert saved["raw_arguments"] == raw and saved["stop_reason"] == "max_tokens" and "stated_confidence" in saved["error"]
    assert saved["output_tokens"] == 1200
    assert run.run_info["rejected_submissions"] == 1 and run.run_info["tokens_used"] == 2000 + 1200 + 2300 + 400


def test_a_submission_that_is_cut_off_twice_is_reported_as_cut_off_in_the_run_problem_and_limitations():
    llm = ScriptedLLM([say(truncated(cause=None), stop="max_tokens"), say(truncated(cause=None), stop="max_tokens")])
    run = run_investigation(llm, "x", tools=stubs()[0])
    assert len(run.rejected) == 2 and run.candidate["component"] == "unknown"
    assert "reply was cut off" in run.run_info["llm_error"] and run.run_info["stop_reason"] == "malformed_submission"
    assert any("reply was cut off" in n for n in run.candidate["limitations"])
    assert "reply was cut off" in run.candidate["cause"]


def test_a_cut_off_reply_with_the_evidence_missing_asks_for_a_shorter_answer_and_keeps_the_cut_off_note():
    llm = ScriptedLLM([say(truncated(), stop="max_tokens"), say(truncated(), stop="max_tokens")])
    run = run_investigation(llm, "x", tools=stubs()[0])
    ask = tool_messages(llm.calls[1])[0]["content"]
    assert "cut off" in ask and "SHORTER" in ask and "evidence is missing" in ask
    assert len(llm.calls) == 2 and len(run.rejected) == 2
    assert run.candidate["component"] == "svc-b" and run.candidate["evidence"] == []
    assert any("reply was cut off" in n for n in run.candidate["limitations"])


def test_a_rejection_that_was_not_cut_off_keeps_the_plain_message_and_is_still_saved():
    llm = ScriptedLLM([say(submit(stated_confidence=85), stop="tool_use"), say(submit())])
    run = run_investigation(llm, "x", tools=stubs()[0])
    ask = tool_messages(llm.calls[1])[0]["content"]
    assert "cut off" not in ask and "SHORTER" not in ask and "corrected arguments" in ask
    assert run.rejected[0]["stop_reason"] == "tool_use" and run.rejected[0]["raw_arguments"]["stated_confidence"] == 85
    assert run.run_info["llm_error"] is None


def test_the_concluding_call_and_the_retry_get_the_larger_cap_but_investigation_turns_do_not():
    config = LoopConfig(step_budget=3)
    llm = ScriptedLLM([say(call("query_logs", window_minutes=5)), say(call("query_logs", window_minutes=6)),
                       say(truncated(cause=None), stop="max_tokens"), say(submit())])
    run = run_investigation(llm, "x", config, stubs()[0])
    assert [c["max_tokens"] for c in llm.calls] == [1200, 1200, 4000, 4000]
    assert run.candidate["component"] == "svc-b"


def test_a_retry_outside_the_wrap_up_also_gets_the_larger_cap():
    llm = ScriptedLLM([say(submit(stated_confidence=85)), say(submit())])
    run_investigation(llm, "x", tools=stubs()[0])
    assert [c["max_tokens"] for c in llm.calls] == [1200, 4000]


def test_the_larger_cap_never_exceeds_what_is_left_of_the_token_budget():
    llm = ScriptedLLM([say(call("query_logs"), usage=(5000, 100)), say(submit(stated_confidence=0.3), usage=(5300, 200))])
    run = run_investigation(llm, "x", LoopConfig(token_budget=12000), stubs()[0])
    cap = llm.calls[1]["max_tokens"]
    assert 1200 <= cap < 4000 and 5100 + 5100 + cap <= 12000
    assert run.run_info["tokens_used"] <= 12000


def test_investigate_saves_rejected_submissions_json_only_when_there_are_some(tmp_path, capsys):
    raw = {"component": "svc-b", "cause": "c"}
    llm = ScriptedLLM([say(call(SUBMIT, **raw), stop="max_tokens"), say(submit())])
    assert main([], llm=llm, runs_dir=tmp_path / "a") == 0
    (folder,) = list((tmp_path / "a").iterdir())
    saved = json.loads((folder / "rejected_submissions.json").read_text())
    assert saved[0]["raw_arguments"] == raw and saved[0]["stop_reason"] == "max_tokens" and saved[0]["error"]
    assert "rejected submissions: 1" in capsys.readouterr().out

    assert main([], llm=ScriptedLLM([say(submit())]), runs_dir=tmp_path / "b") == 0
    (clean,) = list((tmp_path / "b").iterdir())
    assert not (clean / "rejected_submissions.json").exists()


def test_openai_finish_reason_length_is_reported_as_max_tokens():
    from oncall.llm import OpenAIProvider

    class Message:
        content, tool_calls = "hi", None

    class Response:
        choices = [type("C", (), {"message": Message(), "finish_reason": "length"})()]
        usage = None

    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.model = "m"
    provider.client = type("Cl", (), {"chat": type("Ch", (), {"completions": type("Co", (), {"create": staticmethod(lambda **kw: Response())})()})()})()
    assert provider.complete("", [{"role": "user", "content": "go"}], [], 50).stop_reason == "max_tokens"
