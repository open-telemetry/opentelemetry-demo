"""Agent loop, transcript, guards and report tests (no network, scripted model)."""
from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from src.agent.agent import IncidentAgent
from src.agent.guards import confidence_gate, parse_json_object, validate_citations
from src.agent.llm import (LLMError, LLMRateLimitError, LLMResponse, ScriptedSession, ToolCall,
                           call_with_retries)
from src.agent.report import validate_report
from src.agent.tools import ToolBox, strip_flag_data
from src.agent.transcript import Transcript

TRACE = "a" * 32
OTHER_TRACE = "b" * 32


def _res(tool: str, status: str = "ok", evidence=None) -> Dict[str, Any]:
    return {"tool": tool, "status": status, "summary": f"{tool} {status}", "data": {}, "evidence": evidence or []}


def fake_impls(status: str = "ok"):
    return {
        "system_overview": lambda ctx, window_minutes=5: _res("system_overview", status, [
            {"ref": "metric:payment:error_rate", "kind": "metric", "value": 0.42}]),
        "search_traces": lambda ctx, service, **kw: _res("search_traces", status, [
            {"ref": TRACE, "kind": "trace", "service": service}]),
        "search_logs": lambda ctx, **kw: _res("search_logs", status, [
            {"ref": "log:abc", "kind": "log", "text": "payment failed: invalid token"}]),
        "dependency_map": lambda ctx, service: _res("dependency_map", status),
    }


SPECS = [{"name": n, "description": n, "parameters": {"type": "object", "additionalProperties": True}}
         for n in ("system_overview", "search_traces", "search_logs", "dependency_map")]


def toolbox(status: str = "ok") -> ToolBox:
    return ToolBox(ctx=object(), impls=fake_impls(status), specs=SPECS)


def good_diag(**over) -> Dict[str, Any]:
    d = {
        "verdict": "diagnosed",
        "root_cause": {"service": "payment", "category": "errors_on_operation",
                       "summary": "payment Charge fails"},
        "impacted_services": ["checkout", "frontend"], "severity": "HIGH", "confidence": "high",
        "evidence": [{"kind": "trace", "ref": TRACE},
                     {"kind": "metric", "ref": "metric:payment:error_rate", "value": 0.42},
                     {"kind": "log", "ref": "log:abc", "quote": "invalid token"}],
        "alternatives": [{"hypothesis": "checkout itself is broken", "status": "ruled_out",
                          "reason": "deepest failing span is in payment", "refs": [TRACE]}],
        "recommended_next_step": "Page the payment owner.",
    }
    d.update(over)
    return d


def investigation_script(n_calls: int = 3):
    steps = [LLMResponse(tool_calls=[ToolCall("c1", "system_overview", {})])]
    steps.append(LLMResponse(tool_calls=[ToolCall("c2", "search_traces", {"service": "payment"}),
                                         ToolCall("c3", "search_logs", {"service": "payment"})]))
    steps.append(LLMResponse(text="payment is the root cause"))
    return steps


def factory_for(*scripts):
    queue = [ScriptedSession(s) for s in scripts]
    made = []

    def factory(system, tools):
        session = queue.pop(0)
        made.append((system, [t["name"] for t in tools], session))
        return session

    factory.made = made
    return factory


def run_agent(diag_steps, inv_steps=None, status="ok", tmp_path=None, max_calls=12):
    factory = factory_for(inv_steps or investigation_script(), diag_steps)
    agent = IncidentAgent(toolbox(status), factory, max_tool_calls=max_calls, output_dir=tmp_path)
    return agent.run("payment errors", incident_id="TEST-1"), factory


def test_happy_path_records_transcript_and_produces_valid_report(tmp_path):
    t, factory = run_agent([LLMResponse(text=json.dumps(good_diag()))], tmp_path=tmp_path)
    assert [c["tool"] for c in t.tool_calls] == ["system_overview", "search_traces", "search_logs"]
    assert t.findings == "payment is the root cause"
    assert t.gate["final_confidence"] == "high" and not t.gate["escalate"]
    assert t.report["target_service"] == "payment" and t.report["status"] == "DIAGNOSED"
    assert t.report["evidence"]["trace_ids"] == [TRACE]
    assert t.report_schema_valid, t.report_schema_errors
    assert (tmp_path / "TEST-1" / "transcript.json").exists()
    assert (tmp_path / "TEST-1" / "report.json").exists()
    # phase 2 gets no tools; phase 1 gets the tool list
    assert factory.made[0][1] and factory.made[1][1] == []


def test_step_cap_stops_tool_execution():
    looping = [LLMResponse(tool_calls=[ToolCall(f"c{i}", "system_overview", {})]) for i in range(20)]
    t, _ = run_agent([LLMResponse(text=json.dumps(good_diag()))], inv_steps=looping, max_calls=4)
    assert len(t.tool_calls) == 4
    assert t.step_cap_hit


def test_cap_notice_is_sent_to_model():
    inv = [LLMResponse(tool_calls=[ToolCall("c1", "system_overview", {}), ToolCall("c2", "system_overview", {})]),
           LLMResponse(text="done")]
    factory = factory_for(inv, [LLMResponse(text=json.dumps(good_diag()))])
    IncidentAgent(toolbox(), factory, max_tool_calls=1).run("x", incident_id="T")
    session = factory.made[0][2]
    second = session.received[1]
    assert "budget exhausted" in (second["user_text"] or "")
    assert second["tool_results"][1].is_error


def test_fabricated_trace_is_rejected_then_retry_fixes_it():
    bad = good_diag(evidence=[{"kind": "trace", "ref": OTHER_TRACE}])
    t, _ = run_agent([LLMResponse(text=json.dumps(bad)), LLMResponse(text=json.dumps(good_diag()))])
    assert len(t.diagnosis_attempts) == 2
    assert "rejected" in t.diagnosis_attempts[0]["problems"][0]
    assert all(c["valid"] for c in t.citations)
    assert t.gate["final_confidence"] == "high"


def test_fabrication_after_retry_lowers_confidence_and_drops_evidence():
    bad = good_diag(evidence=[{"kind": "trace", "ref": OTHER_TRACE},
                              {"kind": "metric", "ref": "metric:payment:error_rate", "value": 0.99}])
    t, _ = run_agent([LLMResponse(text=json.dumps(bad)), LLMResponse(text=json.dumps(bad))])
    assert t.gate["final_confidence"] == "low" and t.gate["escalate"]
    assert t.report["evidence"]["trace_ids"] == []
    assert OTHER_TRACE not in json.dumps(t.report)
    assert t.report["status"] == "DETECTED"


def test_invented_trace_in_prose_is_caught():
    idx = Transcript("x", "a").evidence_index()
    diag = good_diag(evidence=[], root_cause={"service": "payment", "category": "errors_on_operation",
                                              "summary": f"see trace {OTHER_TRACE}"})
    results = validate_citations(diag, idx)
    assert results and not results[0]["valid"]


def test_malformed_model_output_escalates():
    t, _ = run_agent([LLMResponse(text="I think it's payment"), LLMResponse(text="still not json")])
    assert t.gate["escalate"] and t.gate["final_confidence"] == "low"
    assert any("no parseable diagnosis" in e for e in t.errors)
    assert t.report["status"] == "DETECTED"


def test_single_signal_caps_at_medium_without_alternative():
    diag = good_diag(evidence=[{"kind": "trace", "ref": TRACE}, {"kind": "trace", "ref": "span:" + TRACE + ":1"}],
                     alternatives=[])
    t = Transcript("x", "a")
    t.record_tool("search_traces", {}, _res("search_traces", evidence=[
        {"ref": TRACE, "kind": "trace"}, {"ref": f"span:{TRACE}:1", "kind": "trace"}]))
    gate = confidence_gate(diag, validate_citations(diag, t.evidence_index()), t)
    assert gate["final_confidence"] == "medium" and not gate["escalate"]


def test_unavailable_sources_escalate_even_if_model_is_confident():
    t, _ = run_agent([LLMResponse(text=json.dumps(good_diag(evidence=[])))], status="source_unavailable")
    assert t.gate["escalate"]
    assert "every telemetry source was unavailable or errored" in t.gate["reasons"]


def test_unknown_tool_and_bad_arguments_are_errors_not_crashes():
    box = toolbox()
    assert box.execute("read_flags", {})["status"] == "error"
    strict = ToolBox(ctx=object(), impls=fake_impls(), specs=[
        {"name": "search_traces", "description": "", "parameters": {
            "type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"],
            "additionalProperties": False}}])
    assert strict.execute("search_traces", {})["status"] == "error"


def test_tool_crash_is_reported_as_error():
    box = ToolBox(ctx=object(), impls={"system_overview": lambda ctx, **kw: 1 / 0},
                  specs=[SPECS[0]])
    res = box.execute("system_overview", {})
    assert res["status"] == "error" and "ZeroDivisionError" in res["summary"]


def test_flag_data_is_stripped():
    raw = {"attributes": [{"key": "feature_flag.key", "value": "paymentFailure"},
                          {"key": "http.status_code", "value": 500}],
           "feature_flag.variant": "on", "events": [{"name": "feature_flag", "x": 1}, {"name": "exception"}]}
    clean = strip_flag_data(raw)
    assert "paymentFailure" not in json.dumps(clean) and "feature_flag" not in json.dumps(clean)
    assert clean["attributes"] == [{"key": "http.status_code", "value": 500}]


def test_no_tool_touches_flagd():
    import inspect
    import src.agent.tools as tools_mod
    names = {s["name"] for s in tools_mod.TOOL_SPECS}
    assert not any("flag" in n for n in names)
    src = inspect.getsource(tools_mod)
    assert "8013" not in src and "demo.flagd.json" not in src and "FlagdAdapter" not in src


def test_parse_json_object_handles_fences():
    obj, err = parse_json_object('Here:\n```json\n{"a": 1}\n```')
    assert obj == {"a": 1} and err is None
    assert parse_json_object("nothing")[0] is None


def test_retry_backoff_honours_retry_after_and_gives_up():
    sleeps = []
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("429")
        return "ok"

    assert call_with_retries(flaky, lambda e: (True, True, 1.5), max_retries=5, sleep=sleeps.append) == "ok"
    assert sleeps == [1.5, 1.5]
    with pytest.raises(LLMRateLimitError):
        call_with_retries(lambda: (_ for _ in ()).throw(RuntimeError("429")), lambda e: (True, True, None),
                          max_retries=2, sleep=lambda s: None)
    with pytest.raises(LLMError):
        call_with_retries(lambda: (_ for _ in ()).throw(ValueError("400")), lambda e: (False, False, None),
                          sleep=lambda s: None)


def test_llm_failure_mid_run_escalates_instead_of_crashing():
    def boom(*a):
        raise LLMError("rate limited")

    factory = factory_for([boom], [])
    t = IncidentAgent(toolbox(), factory).run("x", incident_id="T")
    assert t.gate["escalate"] and any("LLM failure" in e for e in t.errors)
    ok, _ = validate_report(t.report)
    assert t.report["status"] == "DETECTED" and not ok  # no trace evidence -> schema minItems unmet, no placeholder


def test_daily_quota_429_fails_fast_without_retrying():
    from src.agent.llm import _is_daily_quota
    sleeps = []
    err = RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    assert _is_daily_quota(err)
    with pytest.raises(LLMRateLimitError):
        call_with_retries(lambda: (_ for _ in ()).throw(err),
                          lambda e: (not _is_daily_quota(e), True, None), sleep=sleeps.append)
    assert sleeps == []



def test_alternative_without_cited_refs_does_not_allow_high():
    t, _ = run_agent([LLMResponse(text=json.dumps(good_diag(alternatives=[
        {"hypothesis": "checkout itself is broken", "status": "ruled_out", "reason": "looks fine"}])))])
    assert t.gate["final_confidence"] == "medium" and not t.gate["alternative_ruled_out"]


def test_alternative_with_unknown_ref_does_not_count():
    t, _ = run_agent([LLMResponse(text=json.dumps(good_diag(alternatives=[
        {"hypothesis": "db down", "status": "ruled_out", "reason": "db ok", "refs": ["metric:db:cpu"]}])))])
    assert t.gate["final_confidence"] == "medium"


def test_cap_result_keeps_evidence_in_step_with_rows():
    from src.agent.tools import cap_result
    rows = [{"name": f"svc{i:02d}", "state": "running", "pad": "x" * 150} for i in range(40)]
    ev = [{"ref": f"container:svc{i:02d}:{k}", "kind": "container", "value": 1}
          for i in range(40) for k in ("state", "restart_count", "exit_code")]
    res = cap_result({"tool": "container_health", "status": "ok", "summary": "", "data": {"containers": rows},
                      "evidence": ev}, max_chars=6000)
    shown = {r["name"] for r in res["data"]["containers"]}
    assert res["truncated"] and len(shown) > 5
    assert {e["ref"].split(":")[1] for e in res["evidence"]} == shown
    assert len(json.dumps(res)) <= 6000


def test_missing_container_is_reported_as_missing_not_unavailable():
    from src.agent.tools import ToolContext, container_health

    def docker(args):
        raise RuntimeError("Error: No such object: ghost")

    ctx = ToolContext(prometheus=object(), jaeger=object(), opensearch=object(), docker_runner=docker)
    res = container_health(ctx, "ghost")
    assert res["status"] == "ok" and res["data"]["containers"][0]["state"] == "missing"


class _FakeJaeger:
    def __init__(self, by_filter):
        self.by_filter = by_filter
        self.calls = []

    def _request(self, method, path, params=None):
        self.calls.append(params)
        return self.by_filter["filtered" if "query.attributes" in params else "plain"]


def _otlp(trace_id, error):
    span = {"traceId": trace_id, "spanId": "s1", "name": "Charge", "startTimeUnixNano": "1",
            "endTimeUnixNano": "2000001", "status": {"code": 2} if error else {}}
    return {"result": {"resourceSpans": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "payment"}}]}, "scopeSpans": [{"spans": [span]}]}]}}


def test_search_traces_uses_error_filter_first():
    from src.agent.tools import ToolContext, search_traces
    jaeger = _FakeJaeger({"filtered": _otlp(TRACE, True), "plain": _otlp(OTHER_TRACE, False)})
    res = search_traces(ToolContext(jaeger=jaeger, prometheus=object(), opensearch=object()), "payment")
    assert res["status"] == "ok" and res["evidence"][0]["ref"] == TRACE
    assert len(jaeger.calls) == 1 and "query.attributes" in jaeger.calls[0]


def test_search_traces_falls_back_to_scan_and_reports_no_data():
    from src.agent.tools import ToolContext, search_traces
    jaeger = _FakeJaeger({"filtered": {"result": {"resourceSpans": []}}, "plain": _otlp(OTHER_TRACE, False)})
    res = search_traces(ToolContext(jaeger=jaeger, prometheus=object(), opensearch=object()), "payment")
    assert res["status"] == "no_data" and len(jaeger.calls) == 2
