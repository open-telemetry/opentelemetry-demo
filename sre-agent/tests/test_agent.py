"""Offline tests (no demo, no LLM, no network). Run: python -m tests.run   (or pytest -q)"""
import json
import os
import tempfile
from pathlib import Path

os.environ["ACTION_API_MODE"] = "mock"

from agent import actions, config, evidence_check, pipeline, rules, runbook, toolbox  # noqa: E402
from agent.investigate import investigate  # noqa: E402
from tests import fixtures as F  # noqa: E402

config.ACTION_API_MODE = "mock"
_tmp = Path(tempfile.mkdtemp())
config.RUNS = _tmp
config.KILL_FILE = _tmp / "KILL"
for mod in (pipeline, actions):
    pass
import agent.memory as memory  # noqa: E402

memory.FILE = _tmp / "memory.jsonl"


def _alert(i="t"):
    return {"incident_id": f"inc-test-{i}", "alert_id": "a1", "fired_at": "2026-10-23T10:00:00+0000",
            "source": "test", "reasons": ["test"], "services": ["checkout"]}


def _diag(snapshot, chat=None):
    s = toolbox.Session(replay=snapshot)
    return investigate(s, _alert(), use_llm=chat is not None, chat=chat, log=lambda *a: None), s


# ---------------------------------------------------------------- rules / deterministic brain
def test_payment_failure_rule_based():
    out, _ = _diag(F.payment_failure())
    d = out["diagnosis"]
    assert d["root_cause"]["service"] == "payment", d
    assert d["root_cause"]["fault_type"] == "application_error"
    assert d["status"] == "diagnosed" and d["confidence"] >= 0.6
    assert all(e["verified"] for e in d["evidence"]), d["evidence"]
    assert any(F.T1 in (e.get("reference") or "") for e in d["evidence"])   # exact trace id cited


def test_stopped_service_blames_callee_not_caller():
    out, _ = _diag(F.payment_stopped())
    rc = out["diagnosis"]["root_cause"]
    assert rc["service"] == "payment", out["meta"]["ranking"][:2]
    assert rc["fault_type"] == "service_down"


def test_cache_down_blames_valkey():
    out, _ = _diag(F.valkey_down())
    rc = out["diagnosis"]["root_cause"]
    assert rc["service"] == "valkey-cart", out["meta"]["ranking"][:2]
    assert rc["fault_type"] == "dependency_unavailable"


def test_high_cpu():
    out, _ = _diag(F.ad_high_cpu())
    rc = out["diagnosis"]["root_cause"]
    assert rc["service"] == "ad" and rc["fault_type"] in ("high_cpu", "latency"), rc


def test_traffic_flood():
    out, _ = _diag(F.traffic_flood())
    rc = out["diagnosis"]["root_cause"]
    assert rc["service"] in ("frontend", "frontend-proxy") and rc["fault_type"] == "traffic_flood", out["meta"]["ranking"]


def test_healthy_system_is_not_an_incident():
    out, _ = _diag(F.healthy())
    d = out["diagnosis"]
    assert d["status"] == "no_incident" and d["confidence"] <= 0.3
    assert runbook.propose(d)["action"] == "escalate"


# ---------------------------------------------------------------- LLM tool loop (scripted fake LLM)
def _fake_llm(script):
    it = iter(script)

    def chat(msgs, tools=None, **kw):
        names = {t["function"]["name"] for t in tools}
        assert "get_service_health" in names and "submit_diagnosis" in names
        return next(it)
    return chat


def _tc(i, name, args):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def test_llm_loop_and_hallucination_check():
    sub = {"root_cause": {"service": "payment", "component": "oteldemo.PaymentService/Charge",
                          "fault_type": "application_error", "summary": "payment Charge fails: invalid token"},
           "confidence": 0.9, "reasoning": "deepest error span is payment Charge",
           "evidence": [
               {"source": "traces", "signal": "error origin payment Charge, 28 spans", "reference": F.T1, "tool_call": 2},
               {"source": "logs", "signal": "payment log", "reference": "Payment request failed. Invalid token.", "tool_call": 3},
               {"source": "metrics", "signal": "payment CPU 99.7% for 31 minutes", "reference": "cpu=99.7"},  # invented
           ],
           "affected_services": ["checkout", "frontend"]}
    script = [_tc(1, "get_service_health", {}), _tc(2, "get_error_origins", {}),
              _tc(3, "search_logs", {"service": "payment"}), _tc(4, "get_trace", {"trace_id": F.T1}),
              _tc(5, "submit_diagnosis", sub)]
    out, s = _diag(F.payment_failure(), chat=_fake_llm(script))
    d = out["diagnosis"]
    assert out["meta"]["llm_used"] and d["root_cause"]["service"] == "payment"
    flags = [e["verified"] for e in d["evidence"]]
    assert flags == [True, True, False], flags            # invented metric caught
    assert out["meta"]["review"]["evidence_unverified"] == 1
    assert [c["name"] for c in s.calls][:4] == ["get_service_health", "get_error_origins", "search_logs", "get_trace"]


def test_llm_invalid_then_fallback():
    bad = _tc(1, "submit_diagnosis", {"root_cause": {"service": "x"}})
    out, _ = _diag(F.payment_failure(), chat=_fake_llm([bad, bad, bad]))
    assert not out["meta"]["llm_used"] and out["meta"]["llm_errors"]
    assert out["diagnosis"]["root_cause"]["service"] == "payment"   # rules fallback still right


def test_evidence_checker_numbers():
    corpus = '{"detail": "error rate 45.0% (baseline 0.0%)", "error_rate": 0.45}'
    assert evidence_check.check_item({"signal": "payment error rate 45%"}, corpus)
    assert not evidence_check.check_item({"signal": "payment error rate 77%"}, corpus)


# ---------------------------------------------------------------- hands
def test_runbook_choices():
    d = {"status": "diagnosed", "root_cause": {"service": "payment", "fault_type": "service_down"}}
    assert runbook.propose(d)["action"] in ("restart_service", "toggle_flag")
    d = {"status": "diagnosed", "root_cause": {"service": "frontend", "fault_type": "traffic_flood"}}
    assert runbook.propose(d)["action"] == "throttle_load"
    d = {"status": "escalated", "escalation_reason": "low", "root_cause": {"service": "ad", "fault_type": "high_cpu"}}
    assert runbook.propose(d)["action"] == "escalate"
    d = {"status": "diagnosed", "root_cause": {"service": "otel-collector", "fault_type": "service_down"}}
    assert runbook.propose(d)["action"] == "escalate"


def test_no_action_without_approval_and_kill_switch():
    r = actions.execute("restart_service", {"service": "payment"}, approval=None)
    assert r["result"] == "refused"
    r = actions.execute("rm_rf", {}, approval={"decision": "approved"})
    assert r["result"] == "refused"
    actions.engage_kill("test")
    try:
        actions.execute("restart_service", {"service": "payment"}, approval={"decision": "approved"})
        assert False, "kill switch did not stop the action"
    except actions.KillSwitchEngaged:
        pass
    finally:
        actions.release_kill()
    r = actions.execute("restart_service", {"service": "payment"}, dry_run=True)
    assert r["result"] == "dry_run" and r["would_send"]["json"] == {"service": "payment"}


def _patch_approval(decision):
    import agent.approval as ap
    orig = ap.ask
    ap.ask = lambda diag, plan, mode="cli": {"decision": decision, "by": "tester", "mode": "test", "at": "now"}
    return lambda: setattr(ap, "ask", orig)


def test_full_loop_resolved():
    undo = _patch_approval("approved")
    try:
        rep = pipeline.run_incident(_alert("full"), use_llm=False, mode="act", replay=F.payment_stopped(),
                                    verify_fn=lambda w, before=None, log=None: {
                                        "recovered": True, "after_seconds": 40, "timeline": [], "before": before},
                                    log=lambda *a: None)
    finally:
        undo()
    assert rep["outcome"] == "resolved", rep["outcome"]
    d = config.RUNS / "inc-test-full"
    for f in ("alert.json", "diagnosis.json", "output.json", "action_plan.json", "approval.json",
              "actions.jsonl", "verification.json", "incident_report.json", "report.md", "snapshot.json"):
        assert (d / f).exists(), f
    assert rep["official_output"]["recovery_verified"] is True
    assert "Incident report" in (d / "report.md").read_text(encoding="utf-8")


def test_full_loop_not_recovered_rolls_back_flood():
    undo = _patch_approval("approved")
    try:
        rep = pipeline.run_incident(_alert("flood"), use_llm=False, mode="act", replay=F.traffic_flood(),
                                    verify_fn=lambda w, before=None, log=None: {
                                        "recovered": False, "after_seconds": 150, "timeline": [], "before": before},
                                    log=lambda *a: None)
    finally:
        undo()
    if rep["diagnosis"]["status"] == "diagnosed":
        assert rep["outcome"] == "not_recovered"
        assert rep["rollback"] and rep["rollback"]["action"] == "throttle_load"


def test_rejected_changes_nothing():
    undo = _patch_approval("rejected")
    try:
        rep = pipeline.run_incident(_alert("rej"), use_llm=False, mode="act", replay=F.payment_failure(),
                                    log=lambda *a: None)
    finally:
        undo()
    assert rep["outcome"] == "rejected" and rep["action_result"] is None


def test_no_flag_reading_anywhere():
    src = "".join(p.read_text(encoding="utf-8") for p in (config.ROOT / "agent").rglob("*.py"))
    assert "demo.flagd.json" not in src and "flag_state" not in src


def test_verify_ignores_lingering_healthcheck_but_not_for_readiness_faults():
    from agent import recovery

    def snap(reasons):
        return lambda: {"eval": {"reasons": reasons}, "health": {}, "errors": []}
    hc = ["container payment unhealthy"]
    v = recovery.verify(["payment"], log=lambda *a: None, snapshot=snap(hc), seconds=1, poll=0,
                        fault_type="application_error")
    assert v["recovered"] and v["warnings"] == hc
    v = recovery.verify(["cart"], log=lambda *a: None, snapshot=snap(["container cart unhealthy"]), seconds=1,
                        poll=0, fault_type="readiness_failure")
    assert not v["recovered"]
    v = recovery.verify(["payment"], log=lambda *a: None, snapshot=snap(["payment error rate 90.0% (baseline 0.0%)"]),
                        seconds=1, poll=0, fault_type="application_error")
    assert not v["recovered"]
