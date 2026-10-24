"""Agent loop, transcript, guards and report tests (no network, scripted model)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from src.agent import llm as llm_mod
from src.agent.agent import IncidentAgent
from src.agent.guards import confidence_gate, parse_json_object, validate_citations
from src.agent.llm import (OPENROUTER_API_URL, AnthropicSession, LLMConfig, LLMConfigError, LLMError,
                           LLMRateLimitError, LLMResponse, OpenAISession, ScriptedSession, ToolCall,
                           call_with_retries, session_factory)
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
    assert t.report["status"] == "DETECTED" and ok
    assert t.report["evidence"]["trace_ids"] == []


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


# --- Root cause vs impacted service for an unreachable dependency -------------------------------
# Sanitized from the live runs (DEMO-001, LIVE-002): checkout's client call to PaymentService/Charge
# fails with a name-resolution error and payment produces no span at all.

UNREACHED_TRACE = "c" * 32


def _span(span_id, parent, name, kind, error=False, message=None, attrs=None):
    sp = {"traceId": UNREACHED_TRACE, "spanId": span_id, "name": name, "kind": kind,
          "startTimeUnixNano": "1000", "endTimeUnixNano": "7000000",
          "status": {"code": 2, "message": message} if error else {},
          "attributes": [{"key": k, "value": {"stringValue": v}} for k, v in (attrs or {}).items()]}
    if parent:
        sp["parentSpanId"] = parent
    return sp


def _trace_payload(resource_spans):
    return {"result": {"resourceSpans": [
        {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": svc}}]},
         "scopeSpans": [{"spans": spans}]} for svc, spans in resource_spans]}}


def unreachable_payment_trace():
    return _trace_payload([
        ("frontend", [_span("f1", None, "oteldemo.CheckoutService/PlaceOrder", 3, True,
                            attrs={"rpc.service": "oteldemo.CheckoutService"})]),
        ("checkout", [
            _span("c1", "f1", "oteldemo.CheckoutService/PlaceOrder", 2, True,
                  "failed to charge card: could not charge the card: rpc error: code = Unavailable"),
            _span("c2", "c1", "oteldemo.PaymentService/Charge", 3, True,
                  "name resolver error: produced zero addresses",
                  {"rpc.method": "oteldemo.PaymentService/Charge"})]),
    ])


def failing_payment_server_trace():
    payload = unreachable_payment_trace()
    payload["result"]["resourceSpans"].append(
        {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "payment"}}]},
         "scopeSpans": [{"spans": [_span("p1", "c2", "charge", 2, True, "Invalid token")]}]})
    return payload


class _TraceJaeger:
    def __init__(self, payload):
        self.payload = payload

    def _request(self, method, path, params=None):
        return self.payload


def _ctx(payload):
    from src.agent.tools import ToolContext
    return ToolContext(jaeger=_TraceJaeger(payload), prometheus=object(), opensearch=object())


def test_get_trace_marks_dependency_that_was_never_reached():
    from src.agent.tools import get_trace
    res = get_trace(_ctx(unreachable_payment_trace()), UNREACHED_TRACE)
    dep = res["data"]["dependency_failure"]
    assert (dep["caller"], dep["dependency"], dep["reached"]) == ("checkout", "payment", False)
    assert "never reached payment" in res["summary"]
    span_ev = next(e for e in res["evidence"] if e["ref"].startswith("span:"))
    assert span_ev["reached"] is False and span_ev["dependency"] == "payment"


def test_search_traces_reports_unreached_dependency():
    from src.agent.tools import search_traces
    res = search_traces(_ctx(unreachable_payment_trace()), "checkout")
    assert res["data"]["traces"][0]["dependency_failure"]["dependency"] == "payment"
    assert "checkout's calls to payment never reached payment" in res["summary"]


def test_dependency_that_answered_with_an_error_is_not_marked_unreached():
    from src.agent.tools import get_trace
    res = get_trace(_ctx(failing_payment_server_trace()), UNREACHED_TRACE)
    assert res["data"]["deepest_failing_span"]["service"] == "payment"
    assert "dependency_failure" not in res["data"]


def test_callee_mapping_covers_grpc_db_and_messaging():
    from src.agent.tools import _callee_of
    assert _callee_of({"name": "oteldemo.CartService/GetCart", "attributes": {}}) == "cart"
    assert _callee_of({"name": "HGET", "attributes": {"db.system": "redis"}}) == "valkey-cart"
    assert _callee_of({"name": "SELECT", "attributes": {"db.system": "postgresql"}}) == "astronomy-db"
    assert _callee_of({"name": "orders publish", "attributes": {"messaging.system": "kafka"}}) == "kafka"
    assert _callee_of({"name": "GET", "attributes": {"server.address": "quote:8090"}}) == "quote"
    assert _callee_of({"name": "internal work", "attributes": {}}) is None


def _unreached_impls():
    span_ref = f"span:{UNREACHED_TRACE}:c2"
    return {
        "search_traces": lambda ctx, service, **kw: _res("search_traces", evidence=[
            {"ref": UNREACHED_TRACE, "kind": "trace", "service": service},
            {"ref": span_ref, "kind": "trace", "service": "checkout", "caller": "checkout",
             "dependency": "payment", "reached": False}]),
        "system_overview": lambda ctx, window_minutes=5: _res("system_overview", evidence=[
            {"ref": "metric:checkout:error_rate", "kind": "metric", "value": 1.0}]),
        "container_health": lambda ctx, service=None: _res("container_health", evidence=[
            {"ref": "container:payment:state", "kind": "container", "value": "running"}]),
    }


def _unreached_diag(root, impacted):
    return {
        "verdict": "diagnosed",
        "root_cause": {"service": root, "category": "dependency_unreachable",
                       "summary": "PaymentService/Charge calls fail with a name resolution error"},
        "impacted_services": impacted, "severity": "HIGH", "confidence": "high",
        "evidence": [{"kind": "trace", "ref": f"span:{UNREACHED_TRACE}:c2"},
                     {"kind": "metric", "ref": "metric:checkout:error_rate", "value": 1.0}],
        "alternatives": [{"hypothesis": "payment container crashed", "status": "ruled_out",
                          "reason": "container is running", "refs": ["container:payment:state"]}],
        "recommended_next_step": "Check how checkout resolves the payment address.",
    }


def _run_unreached(diag_steps):
    specs = [{"name": n, "description": n, "parameters": {"type": "object", "additionalProperties": True}}
             for n in ("system_overview", "search_traces", "container_health")]
    box = ToolBox(ctx=object(), impls=_unreached_impls(), specs=specs)
    inv = [LLMResponse(tool_calls=[ToolCall("1", "system_overview", {}),
                                   ToolCall("2", "search_traces", {"service": "checkout"}),
                                   ToolCall("3", "container_health", {"service": "payment"})]),
           LLMResponse(text="checkout cannot reach payment")]
    return IncidentAgent(box, factory_for(inv, diag_steps)).run("checkout errors", incident_id="UNR")


def test_caller_named_as_root_cause_is_reasked_and_corrected():
    t = _run_unreached([LLMResponse(text=json.dumps(_unreached_diag("checkout", ["frontend"]))),
                        LLMResponse(text=json.dumps(_unreached_diag("payment", ["checkout", "frontend"])))])
    assert "never reached payment" in " ".join(t.diagnosis_attempts[0]["problems"])
    assert t.report["target_service"] == "payment"
    assert "checkout" in t.report["impacted_services"]
    assert t.gate["final_confidence"] == "high" and not t.gate["escalate"]


def test_caller_still_named_after_reask_escalates():
    wrong = LLMResponse(text=json.dumps(_unreached_diag("checkout", ["frontend"])))
    t = _run_unreached([wrong, wrong])
    assert t.gate["escalate"] and t.gate["final_confidence"] == "low"
    assert "root cause names the caller of an unreachable dependency" in t.gate["reasons"]
    assert t.report["status"] == "DETECTED"


def test_dependency_named_first_time_needs_no_reask():
    t = _run_unreached([LLMResponse(text=json.dumps(_unreached_diag("payment", ["checkout"])))])
    assert len(t.diagnosis_attempts) == 1 and t.report["target_service"] == "payment"


# ---------------------------------------------------------------- provider config and token usage

def _usage(prompt, completion):
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}


@pytest.mark.parametrize("cfg, problem", [
    (LLMConfig(provider="unset"), "LLM_PROVIDER is not set"),
    (LLMConfig(provider="mock", api_key="k", model="m"), "not supported"),
    (LLMConfig(provider="anthropic"), "LLM_API_KEY is not set"),
    (LLMConfig(provider="openrouter", model="m"), "LLM_API_KEY is not set"),
    (LLMConfig(provider="openrouter", api_key="k"), "LLM_MODEL must be set"),
    (LLMConfig(provider="openai_compatible", api_key="k", model="m"), "LLM_BASE_URL must be set"),
])
def test_session_factory_refuses_to_run_without_a_configured_model(cfg, problem):
    with pytest.raises(LLMConfigError, match=problem):
        session_factory(cfg)


def test_no_offline_session_can_produce_a_diagnosis(tmp_path, monkeypatch):
    for key in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(LLMConfigError):
        session_factory(LLMConfig.from_env(root_dir=tmp_path))
    assert not hasattr(llm_mod, "AutonomousInvestigationSession")


@pytest.mark.parametrize("provider, base_url", [("openrouter", ""), ("openai_compatible", OPENROUTER_API_URL)])
def test_openrouter_is_served_by_the_openai_session(provider, base_url):
    cfg = LLMConfig(provider=provider, base_url=base_url, model="google/gemini-3.8-flash", api_key="test-key",
                    http_referer="https://example.test", app_title="Incident Zero")
    session = session_factory(cfg)("system", SPECS)
    assert isinstance(session, OpenAISession)
    assert str(session.client.base_url).rstrip("/") == OPENROUTER_API_URL
    assert session.client.default_headers["HTTP-Referer"] == "https://example.test"
    assert session.client.default_headers["X-Title"] == "Incident Zero"


def test_openai_session_caps_output_and_records_reported_token_usage():
    from openai.types.chat import ChatCompletion

    session = OpenAISession(LLMConfig(provider="openrouter", model="m", api_key="test-key", max_tokens=4096),
                            "system", SPECS)
    completion = ChatCompletion.model_validate({
        "id": "gen-1", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "system_overview", "arguments": "{}"}}]}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}})
    replies, sent = [completion, completion.model_copy(update={"usage": None})], []
    session.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: sent.append(kw) or replies.pop(0))))
    resp = session.send(user_text="ALERT")
    assert sent[0]["max_tokens"] == 4096  # uncapped requests are refused with 402 by OpenRouter
    assert resp.tool_calls[0].name == "system_overview"
    assert resp.usage == _usage(120, 30)
    assert session.send(user_text="again").usage is None


def test_anthropic_session_counts_cached_input_as_prompt_tokens():
    from anthropic.types import Message

    session = AnthropicSession(LLMConfig(provider="anthropic", model="claude-haiku-5-5", api_key="test-key"),
                               "system", SPECS)
    message = Message.model_validate({
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
        "content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 50,
                  "cache_creation_input_tokens": 0}})
    session.client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: message))
    assert session.send(user_text="ALERT").usage == _usage(150, 20)


def test_token_usage_is_accumulated_on_the_transcript_and_saved(tmp_path):
    inv = investigation_script()
    inv[0].usage, inv[2].usage = _usage(100, 10), _usage(300, 20)
    diag = [LLMResponse(text=json.dumps(good_diag()), usage=_usage(500, 50))]
    t, _ = run_agent(diag, inv_steps=inv, tmp_path=tmp_path)
    assert t.token_usage == {"requests": 4, "requests_without_usage": 1,
                             "prompt_tokens": 900, "completion_tokens": 80, "total_tokens": 980}
    saved = json.loads((tmp_path / "TEST-1" / "transcript.json").read_text())
    assert saved["token_usage"] == t.token_usage


# ---------------------------------------------------------------- run events

FAKE_KEY = "sk-or-v1-" + "0123456789abcdef" * 4


def test_events_are_emitted_in_order_as_the_run_happens(tmp_path):
    from src.events import EventLog

    events = EventLog(echo=False)
    inv = investigation_script()
    inv[1] = LLMResponse(text="checking traces and logs", tool_calls=inv[1].tool_calls)
    diag = [LLMResponse(text=json.dumps(good_diag()), usage=_usage(500, 50))]
    agent = IncidentAgent(toolbox(), factory_for(inv, diag), output_dir=tmp_path, events=events)
    t = agent.run("payment errors", incident_id="EV-1")
    names = [r["event"] for r in events.records]
    assert names == ["ALERT_RECEIVED", "TOOL_CALL", "MODEL_NOTE", "TOOL_CALL", "TOOL_CALL", "MODEL_NOTE",
                     "DIAGNOSIS", "GATE"]
    assert all(r["incident_id"] == "EV-1" for r in events.records)
    calls = [r for r in events.records if r["event"] == "TOOL_CALL"]
    assert calls[1]["summary"].startswith("#2 search_traces(service=payment) -> ok:")
    assert set(calls[0]["data"]) == {"n", "tool", "arguments", "status", "summary"}
    diag_ev = next(r for r in events.records if r["event"] == "DIAGNOSIS")["data"]
    assert (diag_ev["verdict"], diag_ev["service"], diag_ev["category"]) == \
        ("diagnosed", "payment", "errors_on_operation")
    gate = events.records[-1]["data"]
    assert gate["escalate"] is False and gate["final_confidence"] == t.gate["final_confidence"]
    assert gate["token_usage"]["total_tokens"] == 550


def test_events_record_llm_failure_as_error_then_gate():
    from src.events import EventLog

    def boom(*a):
        raise LLMError("rate limited")

    events = EventLog(echo=False)
    IncidentAgent(toolbox(), factory_for([boom], []), events=events).run("x", incident_id="EV-2")
    assert [r["event"] for r in events.records] == ["ALERT_RECEIVED", "ERROR", "GATE"]
    assert events.records[-1]["data"]["escalate"] is True


def test_events_never_contain_the_api_key_or_flag_data():
    from src.events import EventLog

    inv = [LLMResponse(text=f"using key {FAKE_KEY}", tool_calls=[
               ToolCall("c1", "search_traces", {"service": "payment", "api_key": FAKE_KEY,
                                                "feature_flag.key": "paymentFailure"})]),
           LLMResponse(text=f"done, Bearer {FAKE_KEY}")]
    events = EventLog(echo=False)
    IncidentAgent(toolbox(), factory_for(inv, [LLMResponse(text=json.dumps(good_diag()))]),
                  events=events).run("payment errors", incident_id="EV-3")
    dumped = json.dumps(events.records)
    assert FAKE_KEY not in dumped
    assert "paymentFailure" not in dumped and "feature_flag" not in dumped


# ---------------------------------------------------------------- reviewer pass

def _review_reply(verdict, reasons=("evidence points elsewhere",)):
    return LLMResponse(text=json.dumps({"verdict": verdict, "reasons": list(reasons), "refs": [],
                                        "better_alternative": None}), usage=_usage(300, 30))


def test_refuting_review_caps_confidence_at_low_and_escalates():
    from src.events import EventLog

    events = EventLog(echo=False)
    factory = factory_for(investigation_script(), [LLMResponse(text=json.dumps(good_diag()))],
                          [_review_reply("refuted")])
    t = IncidentAgent(toolbox(), factory, events=events).run("payment errors", incident_id="RV-1")
    assert factory.made[2][1] == []
    assert t.gate["final_confidence"] == "low" and t.gate["escalate"] is True
    assert t.gate["review"]["verdict"] == "refuted" and t.gate["review"]["confidence_before"] == "high"
    assert t.token_usage["total_tokens"] == 330
    gate = events.records[-1]
    assert gate["event"] == "GATE" and "review=refuted" in gate["summary"]
    assert gate["data"]["review"]["verdict"] == "refuted" and gate["data"]["escalate"] is True


def test_review_llm_failure_leaves_gate_unchanged_and_marks_review_unavailable():
    def boom(*a):
        raise LLMError("reviewer down")

    t = IncidentAgent(toolbox(), factory_for(investigation_script(), [LLMResponse(text=json.dumps(good_diag()))],
                                             [boom])).run("payment errors", incident_id="RV-2")
    assert t.gate["final_confidence"] == "high" and t.gate["escalate"] is False
    assert t.gate["review"]["verdict"] == "unavailable"


def test_review_never_raises_confidence_or_clears_an_escalation():
    diag = good_diag(verdict="escalate")
    t = IncidentAgent(toolbox(), factory_for(investigation_script(), [LLMResponse(text=json.dumps(diag))],
                                             [_review_reply("upheld", [])])).run("x", incident_id="RV-3")
    assert t.gate["escalate"] is True and t.gate["review"]["verdict"] == "upheld"
    assert t.gate["review"]["confidence_after"] == t.gate["review"]["confidence_before"]


def test_openrouter_out_of_credit_402_escalates_without_a_diagnosis():
    import httpx2
    import openai

    from src.events import EventLog

    body = {"error": {"message": "This request would exceed your available credits given your current "
                                 "in-flight requests. Retry after in-flight requests settle, or add credits.",
                      "code": 402, "metadata": {"reason": "in_flight_budget_exhausted"}}}
    calls = []

    def create(**kw):
        calls.append(kw)
        request = httpx2.Request("POST", OPENROUTER_API_URL + "/chat/completions")
        raise openai.APIStatusError(f"Error code: 402 - {body}", response=httpx2.Response(402, request=request, json=body),
                                    body=body)

    def factory(system, tools):
        session = OpenAISession(LLMConfig(provider="openrouter", model="m", api_key="test-key", max_tokens=4096),
                                system, tools)
        session.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return session

    events = EventLog(echo=False)
    t = IncidentAgent(toolbox(), factory, events=events).run("payment errors", incident_id="EV-402")
    assert len(calls) == 1  # a 402 is not retried
    assert t.diagnosis is None and t.tool_calls == []
    assert [r["event"] for r in events.records] == ["ALERT_RECEIVED", "ERROR", "GATE"]
    assert events.records[1]["data"]["source"] == "llm"
    gate = events.records[-1]["data"]
    assert gate["escalate"] is True and gate["final_confidence"] == "low" and gate["review"] is None
    assert any("402" in r and "credits" in r for r in gate["reasons"])


# ---------------------------------------------------------------- model fallback

def _status_error(code, message="upstream error"):
    import httpx2
    import openai

    body = {"error": {"message": message, "code": code}}
    request = httpx2.Request("POST", OPENROUTER_API_URL + "/chat/completions")
    return openai.APIStatusError(f"Error code: {code} - {body}", response=httpx2.Response(code, request=request,
                                                                                          json=body), body=body)


def _completion(text="", tool_calls=None):
    from openai.types.chat import ChatCompletion

    return ChatCompletion.model_validate({
        "id": "gen-1", "object": "chat.completion", "created": 0, "model": "served",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {
            "role": "assistant", "content": text, "tool_calls": tool_calls}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})


def _fallback_session(replies, fallbacks=("b", "c")):
    cfg = LLMConfig(provider="openrouter", model="a", api_key="test-key", max_tokens=4096, max_retries=0,
                    fallback_models=tuple(fallbacks))
    session = OpenAISession(cfg, "system", SPECS)
    sent = []

    def create(**kw):
        sent.append(kw["model"])
        reply = replies[kw["model"]].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    session.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return session, sent


def test_fallback_models_are_tried_in_order_on_transport_failures_and_stick():
    import openai

    timeout = openai.APITimeoutError(request=__import__("httpx2").Request("POST", OPENROUTER_API_URL))
    session, sent = _fallback_session({"a": [_status_error(429, "free-models-per-min")],
                                       "b": [timeout], "c": [_completion("ok"), _completion("again")]})
    assert session.send(user_text="ALERT").model == "c"
    assert session.send(user_text="more").model == "c"
    assert sent == ["a", "b", "c", "c"]


@pytest.mark.parametrize("code", [402, 404, 500, 503])
def test_each_transport_status_falls_back(code):
    session, sent = _fallback_session({"a": [_status_error(code)], "b": [_completion("ok")]}, ["b"])
    assert session.send(user_text="x").model == "b" and sent == ["a", "b"]


def test_client_errors_do_not_fall_back():
    session, sent = _fallback_session({"a": [_status_error(400, "bad request")]})
    with pytest.raises(LLMError):
        session.send(user_text="x")
    assert sent == ["a"]


def test_malformed_model_output_never_triggers_a_fallback():
    bad = _completion(None, [{"id": "c1", "type": "function", "function": {"name": "system_overview",
                                                                          "arguments": "{not json"}}])
    session, sent = _fallback_session({"a": [bad, _completion("not a diagnosis")], "b": [], "c": []})
    resp = session.send(user_text="x")
    assert resp.model == "a" and resp.tool_calls[0].invalid_arguments == "{not json"
    assert session.send(user_text="y").text == "not a diagnosis" and sent == ["a", "a"]


def test_all_models_failing_escalates_with_every_failure_listed_and_no_diagnosis():
    from src.events import EventLog

    def factory(system, tools):
        session, _ = _fallback_session({"a": [_status_error(429, "free-models-per-day")],
                                        "b": [_status_error(503)], "c": [_status_error(402, "add credits")]})
        return session

    events = EventLog(echo=False)
    t = IncidentAgent(toolbox(), factory, events=events).run("payment errors", incident_id="FB-1")
    assert t.diagnosis is None and [r["event"] for r in events.records] == ["ALERT_RECEIVED", "ERROR", "GATE"]
    reason = events.records[-1]["data"]["reasons"][0]
    assert events.records[-1]["data"]["escalate"] is True
    assert "all models failed" in reason and all(f"{m}: " in reason for m in "abc")


def test_answering_model_is_recorded_on_transcript_and_diagnosis_event():
    from src.events import EventLog

    inv = [LLMResponse(text="payment is the root cause", model="nvidia/x:free")]
    diag = [LLMResponse(text=json.dumps(good_diag()), model="poolside/y:free")]
    events = EventLog(echo=False)
    t = IncidentAgent(toolbox(), factory_for(inv, diag), events=events).run("payment errors", incident_id="FB-2")
    assert t.models_used == ["nvidia/x:free", "poolside/y:free"]
    assert next(r for r in events.records if r["event"] == "DIAGNOSIS")["data"]["model"] == "poolside/y:free"


def test_fallback_models_are_read_from_env(monkeypatch):
    monkeypatch.setenv("LLM_FALLBACK_MODELS", " b:free, ,c:free ")
    assert LLMConfig.from_env().fallback_models == ("b:free", "c:free")


def _provider_fallback_session(primary, secondary, fallback_models=("g",)):
    cfg = LLMConfig(provider="openai_compatible", base_url=OPENROUTER_API_URL, model="a", api_key="test-key",
                    max_tokens=4096, max_retries=0, fallback_provider="gemini", fallback_api_key="gem-key",
                    fallback_provider_models=tuple(fallback_models))
    session = OpenAISession(cfg, "system", SPECS)
    sent = []

    def fake(replies, who):
        def create(**kw):
            sent.append((who, kw["model"], kw))
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    session.client = fake(primary, "openrouter")
    session.targets = [(fake(secondary, "gemini") if c is not None else None, m, p) for c, m, p in session.targets]
    return session, sent


def test_second_provider_takes_over_after_every_primary_model_fails_and_sticks():
    tool_call = [{"id": "c1", "type": "function", "function": {"name": "system_overview", "arguments": "{}"}}]
    from openai.types.chat import ChatCompletion

    first = ChatCompletion.model_validate({
        "id": "gen-1", "object": "chat.completion", "created": 0, "model": "served",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {
            "role": "assistant", "content": "", "tool_calls": tool_call, "reasoning": "provider-only field"}}]})
    session, sent = _provider_fallback_session([first, _status_error(429, "free-models-per-day")],
                                               [_completion("from gemini"), _completion("again")])
    assert session.send(user_text="ALERT").model == "a"
    from src.agent.llm import ToolResultMessage
    resp = session.send(tool_results=[ToolResultMessage("c1", "ok")])
    assert resp.model == "g" and resp.text == "from gemini"
    assert session.send(user_text="more").model == "g"
    assert [(who, m) for who, m, _ in sent] == [("openrouter", "a"), ("openrouter", "a"),
                                                ("gemini", "g"), ("gemini", "g")]
    gemini_messages = sent[2][2]["messages"]
    assert all(set(m) <= {"role", "content", "tool_calls", "tool_call_id", "name"} for m in gemini_messages)
    assert gemini_messages[2]["tool_calls"][0]["function"]["name"] == "system_overview"
    assert sent[2][2]["max_tokens"] == 4096


def test_second_provider_is_not_used_for_bad_requests():
    session, sent = _provider_fallback_session([_status_error(400, "bad request")], [_completion("never")])
    with pytest.raises(LLMError):
        session.send(user_text="x")
    assert [who for who, _, _ in sent] == ["openrouter"]


def test_all_providers_failing_lists_every_model():
    session, _ = _provider_fallback_session([_status_error(429, "free-models-per-day")],
                                            [_status_error(429, "RESOURCE_EXHAUSTED PerDay")])
    with pytest.raises(LLMError) as exc:
        session.send(user_text="x")
    assert "all models failed" in str(exc.value) and "a: " in str(exc.value) and "g: " in str(exc.value)


def test_fallback_provider_is_read_from_env_with_gemini_default_model(monkeypatch):
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "Gemini")
    monkeypatch.setenv("LLM_FALLBACK_API_KEY", "gem-key")
    monkeypatch.setenv("LLM_FALLBACK_MODELS_2", "")
    cfg = LLMConfig.from_env()
    assert cfg.fallback_provider == "gemini" and cfg.fallback_api_key == "gem-key"
    session = OpenAISession(LLMConfig(provider="openrouter", model="a", api_key="k", fallback_provider="gemini",
                                      fallback_api_key="gem-key"), "system", SPECS)
    assert [(m, p) for _, m, p in session.targets] == [("a", "openrouter"), ("gemini-3.5-flash", "gemini")]


def test_no_fallback_provider_without_its_key():
    session = OpenAISession(LLMConfig(provider="openrouter", model="a", api_key="k", fallback_provider="gemini"),
                            "system", SPECS)
    assert [m for _, m, _ in session.targets] == ["a"]


def test_a_providers_own_reply_fields_go_back_to_it_unchanged():
    from src.agent.llm import ToolResultMessage

    tool_call = [{"id": "g1", "type": "function", "function": {"name": "system_overview", "arguments": "{}"}}]
    from openai.types.chat import ChatCompletion

    gemini_reply = ChatCompletion.model_validate({
        "id": "gen-1", "object": "chat.completion", "created": 0, "model": "served",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {
            "role": "assistant", "content": "", "tool_calls": tool_call,
            "extra_content": {"google": {"thought_signature": "sig"}}}}]})
    session, sent = _provider_fallback_session([_status_error(503)], [gemini_reply, _completion("done")])
    session.send(user_text="ALERT")
    session.send(tool_results=[ToolResultMessage("g1", "ok")])
    replayed = sent[-1][2]["messages"][2]
    assert replayed["extra_content"] == {"google": {"thought_signature": "sig"}}
    assert "_provider" not in replayed
