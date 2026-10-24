"""Evaluation harness: case validation, scoring, isolation of expected answers, outputs."""
from __future__ import annotations

import json

import pytest

from src.agent import eval_harness as eh
from src.agent.agent import IncidentAgent
from src.agent.llm import LLMRateLimitError, LLMResponse, ScriptedSession
from tests.test_agent_loop import good_diag, investigation_script, toolbox

CASE = {"id": "p1", "official": True, "source": "mentor", "inject": ["inject", "paymentFailure"],
        "alert": "Error rate above 5% on checkout",
        "expected": {"service": "payment", "category": "errors_on_operation"}}


def case(**over):
    c = json.loads(json.dumps(CASE))
    c.update(over)
    return c


# ---------------------------------------------------------------- case validation

def test_parse_cases_accepts_a_valid_case():
    [c] = eh.parse_cases([case()])
    assert c.id == "p1" and c.official and c.reset == ["reset"] and c.warmup_seconds == 90


@pytest.mark.parametrize("raw, problem", [
    ([], "non-empty"),
    ({"id": "p1"}, "non-empty JSON list"),
    ([case(), "not a case"], "not an object"),
    ([case(alert="")], "'alert' is required"),
    ([case(expected={})], "'expected.service' is required"),
    ([case(expected={"service": "payment", "category": "made_up"})], "is not one of"),
    ([case(), case()], "duplicate id"),
    ([case(secret_hint="payment")], "unknown keys"),
    ([case(alert="paymentFailure is on, check checkout")], "alert text reveals"),
    ([case(alert="errors_on_operation on checkout")], "alert text reveals"),
])
def test_parse_cases_rejects_bad_cases(raw, problem):
    with pytest.raises(eh.CaseError, match=problem):
        eh.parse_cases(raw)


def test_inject_is_required_only_when_faultctl_injects():
    c = case()
    del c["inject"]
    with pytest.raises(eh.CaseError, match="'inject' is required"):
        eh.parse_cases([c], require_inject=True)
    assert eh.parse_cases([c])[0].inject == []


# ---------------------------------------------------------------- scoring

def run_real_agent(tmp_path, diag_steps, inv_steps=None, status="ok"):
    queue = [ScriptedSession(inv_steps or investigation_script()), ScriptedSession(diag_steps)]
    counter = eh.CountingFactory(lambda system, tools: queue.pop(0))
    agent = IncidentAgent(toolbox(status), counter, output_dir=tmp_path)
    return agent, counter


def test_correct_diagnosis_passes_and_counts_requests(tmp_path):
    agent, counter = run_real_agent(tmp_path, [LLMResponse(text=json.dumps(good_diag()))])
    rows = eh.run_cases(eh.parse_cases([case()]), lambda a, i: agent.run(a, incident_id=i),
                        counter, None, "S", tmp_path, log=lambda _: None)
    row = rows[0]
    assert row["outcome"] == "PASS", row
    assert row["expected"] == {"service": "payment", "category": "errors_on_operation"}
    assert row["observed"]["service"] == "payment" and row["checks"]["schema_valid"]
    assert row["llm_requests"] == 4  # 3 investigation turns + 1 diagnosis
    assert (tmp_path / "p1-S" / "transcript.json").exists() and (tmp_path / "p1-S" / "report.json").exists()


def test_wrong_service_is_fail_with_both_answers_recorded(tmp_path):
    diag = good_diag(root_cause={"service": "checkout", "category": "errors_on_operation", "summary": "x"})
    agent, counter = run_real_agent(tmp_path, [LLMResponse(text=json.dumps(diag))])
    [row] = eh.run_cases(eh.parse_cases([case()]), lambda a, i: agent.run(a, incident_id=i),
                         counter, None, "S", tmp_path, log=lambda _: None)
    assert row["outcome"] == "FAIL"
    assert row["expected"]["service"] == "payment" and row["observed"]["service"] == "checkout"
    assert "expected payment" in row["detail"]


def test_wrong_category_is_fail(tmp_path):
    diag = good_diag(root_cause={"service": "payment", "category": "cpu_saturation", "summary": "x"})
    agent, counter = run_real_agent(tmp_path, [LLMResponse(text=json.dumps(diag))])
    [row] = eh.run_cases(eh.parse_cases([case()]), lambda a, i: agent.run(a, incident_id=i),
                         counter, None, "S", tmp_path, log=lambda _: None)
    assert row["outcome"] == "FAIL" and row["checks"]["service_match"] and not row["checks"]["category_match"]


def test_model_failure_is_error_model_not_pass(tmp_path):
    def quota(*_):
        raise LLMRateLimitError("daily quota exceeded")
    agent, counter = run_real_agent(tmp_path, [quota])
    [row] = eh.run_cases(eh.parse_cases([case()]), lambda a, i: agent.run(a, incident_id=i),
                         counter, None, "S", tmp_path, log=lambda _: None)
    assert row["outcome"] == "ERROR_MODEL"


def test_unparseable_diagnosis_is_error_model(tmp_path):
    agent, counter = run_real_agent(tmp_path, [LLMResponse(text="no json"), LLMResponse(text="still none")])
    [row] = eh.run_cases(eh.parse_cases([case()]), lambda a, i: agent.run(a, incident_id=i),
                         counter, None, "S", tmp_path, log=lambda _: None)
    assert row["outcome"] == "ERROR_MODEL"


def test_all_sources_unavailable_is_error_infra(tmp_path):
    agent, counter = run_real_agent(tmp_path, [LLMResponse(text=json.dumps(good_diag()))],
                                    status="source_unavailable")
    [row] = eh.run_cases(eh.parse_cases([case()]), lambda a, i: agent.run(a, incident_id=i),
                         counter, None, "S", tmp_path, log=lambda _: None)
    assert row["outcome"] == "ERROR_INFRA"


class FakeTranscript:
    def __init__(self, diag, gate, schema_valid=True, schema_errors=(), errors=(), statuses=("ok",)):
        self.diagnosis, self.gate = diag, gate
        self.report_schema_valid, self.report_schema_errors = schema_valid, list(schema_errors)
        self.errors = list(errors)
        self.tool_calls = [{"result": {"status": s}} for s in statuses]
        self.step_cap_hit = False


def test_escalation_is_never_a_pass():
    t = FakeTranscript(good_diag(), {"escalate": True, "final_confidence": "low", "reasons": ["weak"]})
    assert eh.score({"service": "payment"}, t)["outcome"] == "ESCALATED"


def test_right_answer_with_invalid_report_is_error_schema():
    t = FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high"},
                       schema_valid=False, schema_errors=["evidence.trace_ids: [] is too short"])
    out = eh.score({"service": "payment"}, t)
    assert out["outcome"] == "ERROR_SCHEMA" and "too short" in out["detail"]
    assert out["checks"]["diagnosis_correct"] and not out["checks"]["schema_valid"]


def test_category_is_optional_in_expected():
    t = FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high"})
    assert eh.score({"service": "payment"}, t)["outcome"] == "PASS"


def test_pass_records_every_check():
    t = FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high", "invalid_citations": 0})
    out = eh.score({"service": "payment", "category": "errors_on_operation"}, t)
    assert out["outcome"] == "PASS"
    assert out["observed"]["service"] == "payment" and out["observed"]["confidence"] == "high"
    checks = out["checks"]
    assert checks["diagnosis_correct"] and checks["service_match"] and checks["category_match"]
    assert checks["schema_valid"] and checks["citations_valid"]


def test_right_answer_with_invalid_citations_is_not_a_pass():
    t = FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "medium", "invalid_citations": 2})
    out = eh.score({"service": "payment"}, t)
    assert out["outcome"] == "FAIL_INVALID_CITATIONS"
    assert out["checks"]["diagnosis_correct"] and not out["checks"]["citations_valid"]
    assert out["invalid_citations"] == 2


def test_missing_root_cause_is_no_diagnosis():
    t = FakeTranscript(None, {"escalate": False, "final_confidence": "low"}, schema_valid=False)
    out = eh.score({"service": "payment"}, t)
    assert out["outcome"] == "NO_DIAGNOSIS"
    assert not out["checks"]["diagnosis_correct"] and out["observed"]["service"] is None


# ---------------------------------------------------------------- isolation and faultctl

def test_agent_receives_only_the_alert(tmp_path):
    seen = []

    def fake_agent(alert, incident_id):
        seen.append((alert, incident_id))
        return FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high"})

    eh.run_cases(eh.parse_cases([case()]), fake_agent, eh.CountingFactory(lambda s, t: None), None, "S",
                 tmp_path, log=lambda _: None)
    assert seen == [("Error rate above 5% on checkout", "p1-S")]
    assert "payment" not in seen[0][0] and "paymentFailure" not in seen[0][1]


def test_faultctl_order_and_reset_after_crash(tmp_path):
    calls = []

    def faultctl(args):
        calls.append(args)
        return ""

    def crashing_agent(alert, incident_id):
        raise RuntimeError("boom")

    [row] = eh.run_cases(eh.parse_cases([case()]), crashing_agent, eh.CountingFactory(lambda s, t: None),
                         faultctl, "S", tmp_path, sleep=lambda _: None, log=lambda _: None)
    assert calls == [["reset"], ["inject", "paymentFailure"], ["reset"]]
    assert row["outcome"] == "ERROR_INFRA" and "boom" in row["detail"]


def test_faultctl_failure_is_error_infra_and_agent_not_run(tmp_path):
    def faultctl(args):
        if args[0] == "inject":
            raise eh.FaultctlError("faultctl inject exited 1: no such incident")
        return ""

    ran = []
    [row] = eh.run_cases(eh.parse_cases([case()]), lambda a, i: ran.append(a),
                         eh.CountingFactory(lambda s, t: None), faultctl, "S", tmp_path,
                         sleep=lambda _: None, log=lambda _: None)
    assert row["outcome"] == "ERROR_INFRA" and "no such incident" in row["detail"] and not ran


def test_faultctl_runner_reports_nonzero_exit():
    with pytest.raises(eh.FaultctlError, match="exited 3"):
        eh.faultctl_runner("sh -c 'echo nope >&2; exit 3'")(["inject", "x"])


# ---------------------------------------------------------------- outputs and CLI guards

def test_write_outputs_produces_machine_readable_summary(tmp_path):
    rows = [{"id": "a", "official": True, "outcome": "PASS", "llm_requests": 9},
            {"id": "b", "official": False, "outcome": "FAIL", "llm_requests": 11},
            {"id": "c", "official": True, "outcome": "ERROR_MODEL", "llm_requests": 2}]
    summary = eh.write_outputs(tmp_path, rows, {"model": "m"})
    on_disk = json.loads((tmp_path / "summary.json").read_text())
    assert on_disk == summary
    assert summary["outcomes"]["PASS"] == 1 and summary["outcomes"]["FAIL"] == 1
    assert summary["official_cases"] == 2 and summary["official_passed"] == 1
    assert summary["llm_requests_total"] == 22
    assert summary["reset_errors"] == 0
    assert json.loads((tmp_path / "results.json").read_text())[1]["id"] == "b"


def test_reset_failure_is_recorded_and_counted(tmp_path):
    def faultctl(args):
        if args == ["reset"] and calls:
            raise eh.FaultctlError("faultctl reset exited 1: busy")
        calls.append(args)
        return ""

    calls = []
    fake_agent = lambda a, i: FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high"})
    rows = eh.run_cases(eh.parse_cases([case()]), fake_agent, eh.CountingFactory(lambda s, t: None),
                        faultctl, "S", tmp_path, sleep=lambda _: None, log=lambda _: None)
    assert rows[0]["outcome"] == "PASS" and "busy" in rows[0]["reset_error"]
    assert eh.summarize(rows)["reset_errors"] == 1


def test_cli_requires_faultctl_unless_no_inject(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FAULTCTL_CMD", raising=False)
    f = tmp_path / "cases.json"
    f.write_text(json.dumps([case()]))
    assert eh.main([str(f)]) == 2
    assert "BLOCKED: FAULTCTL_CMD is not set" in capsys.readouterr().err


def test_cli_missing_cases_file_is_blocked(tmp_path, capsys):
    assert eh.main([str(tmp_path / "nope.json")]) == 2
    assert "BLOCKED: cases file" in capsys.readouterr().err


def test_cli_rejects_malformed_json(tmp_path, capsys):
    f = tmp_path / "cases.json"
    f.write_text("{malformed: json")
    assert eh.main([str(f)]) == 2
    assert "eval_harness:" in capsys.readouterr().err


def test_cli_rejects_unknown_only_ids(tmp_path, capsys):
    f = tmp_path / "cases.json"
    f.write_text(json.dumps([case()]))
    assert eh.main([str(f), "--no-inject", "--only", "p9"]) == 2
    assert "unknown case ids" in capsys.readouterr().err


def test_cli_no_inject_needs_exactly_one_case(tmp_path, capsys):
    f = tmp_path / "cases.json"
    f.write_text(json.dumps([case(), case(id="p2")]))
    assert eh.main([str(f), "--no-inject"]) == 2
    assert "exactly one case" in capsys.readouterr().err


def test_cli_rejects_invalid_cases_file(tmp_path, capsys):
    f = tmp_path / "cases.json"
    f.write_text(json.dumps([case(expected={})]))
    assert eh.main([str(f), "--no-inject"]) == 2
    assert "expected.service" in capsys.readouterr().err


# ---------------------------------------------------------------- tester findings D1-D8

@pytest.mark.parametrize("raw, problem", [
    ([case(expected={"service": "payment", "categroy": "errors_on_operation"})], "unknown expected keys"),  # D1
    ([case(warmup_seconds="abc")], "non-negative integer"),                                                # D2
    ([case(warmup_seconds=None)], "non-negative integer"),
    ([case(warmup_seconds=-5)], "non-negative integer"),                                                   # D3
    ([case(warmup_seconds=True)], "non-negative integer"),
    ([case(alert=42)], "must be a string"),
    ([case(expected={"service": "payment", "category": ["errors_on_operation"]})], "is not one of"),
    ([case(expected={"service": 7})], "expected.service"),
    ([case(official="false")], "'official' must be true or false"),
    ([case(reset="reset")], "'reset' must be a list"),
    ([case(reset=[])], "'reset' must not be empty"),
    ([case(source=3)], "'source' must be a string"),
    ([case(id="a/b")], "may only use letters"),                                                            # D5
    ([case(id="../x")], "may only use letters"),
])
def test_parse_cases_rejects_bad_types(raw, problem):
    with pytest.raises(eh.CaseError, match=problem):
        eh.parse_cases(raw)


@pytest.mark.parametrize("alert, inject", [                                                                # D4
    ("payment failure seen on checkout", ["inject", "paymentFailure"]),
    ("payment-failure on checkout", ["inject", "paymentFailure"]),
    ("PAYMENT_FAILURE on checkout", ["inject", "paymentFailure"]),
    ("paymentfailure on checkout", ["inject", "paymentFailure"]),
    ("paymentFailure is on", ["paymentFailure"]),
    ("ad service is slow", ["inject", "ad"]),
    ("errors-on-operation in checkout", ["inject", "x1"]),
])
def test_leak_check_normalises_spelling(alert, inject):
    with pytest.raises(eh.CaseError, match="alert text reveals"):
        eh.parse_cases([case(alert=alert, inject=inject)])


def test_leak_check_ignores_faultctl_verbs_and_unrelated_short_words():
    [c] = eh.parse_cases([case(alert="Error rate above 5% on checkout after reset", inject=["inject", "ad"])])
    assert c.inject == ["inject", "ad"]


def test_cli_non_utf8_cases_file_exits_2(tmp_path, capsys):                                                # D2
    f = tmp_path / "cases.json"
    f.write_bytes(b"\xff\xfe[\x00")
    assert eh.main([str(f), "--no-inject"]) == 2
    err = capsys.readouterr().err
    assert "eval_harness:" in err and "Traceback" not in err


def test_reset_failure_warns_loudly(tmp_path):                                                             # D6
    logged = []

    def faultctl(args):
        if args == ["reset"] and calls:
            raise eh.FaultctlError("faultctl reset exited 1")
        calls.append(args)
        return ""

    calls = []
    fake_agent = lambda a, i: FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high"})
    eh.run_cases(eh.parse_cases([case()]), fake_agent, eh.CountingFactory(lambda s, t: None), faultctl, "S",
                 tmp_path, sleep=lambda _: None, log=logged.append)
    assert any(line.startswith("WARNING: reset after p1 FAILED") for line in logged)


def test_cli_reset_failure_returns_nonzero(tmp_path, monkeypatch, capsys):                                 # D6
    f = tmp_path / "cases.json"
    f.write_text(json.dumps([case()]))
    monkeypatch.setenv("FAULTCTL_CMD", "fake")
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path / "out"))
    resets = []

    def runner(base):
        def run(args):
            if args == ["reset"]:
                resets.append(1)
                if len(resets) == 2:
                    raise eh.FaultctlError("reset exited 1")
            return ""
        return run

    monkeypatch.setattr(eh, "faultctl_runner", runner)
    monkeypatch.setattr(eh, "run_cases", _real_run_cases_with_fake_agent)
    import src.agent.llm as llm_mod
    monkeypatch.setattr(llm_mod.LLMConfig, "from_env", classmethod(lambda cls, root_dir=None: cls(provider="x")))
    monkeypatch.setattr(llm_mod, "session_factory", lambda cfg=None: (lambda s, t: None))
    assert eh.main([str(f)]) == 1
    assert "reset(s) failed" in capsys.readouterr().err


_ORIGINAL_RUN_CASES = eh.run_cases


def _real_run_cases_with_fake_agent(cases, run_agent, counter, faultctl, stamp, out_dir, **kw):
    fake = lambda a, i: FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high"})
    return _ORIGINAL_RUN_CASES(cases, fake, counter, faultctl, stamp, out_dir, sleep=lambda _: None,
                               log=lambda _: None, **kw)


def test_rows_are_appended_as_each_case_finishes(tmp_path):                                                # D7
    def agent(alert, incident_id):
        if incident_id.startswith("p2"):
            raise KeyboardInterrupt
        return FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high"})

    with pytest.raises(KeyboardInterrupt):
        eh.run_cases(eh.parse_cases([case(), case(id="p2")]), agent, eh.CountingFactory(lambda s, t: None),
                     None, "S", tmp_path, log=lambda _: None)
    rows = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert [r["id"] for r in rows] == ["p1"] and rows[0]["outcome"] == "PASS"


@pytest.mark.parametrize("summaries, outcome", [                                                           # D8
    (["Unknown tool 'x'. Allowed: a.", "Invalid arguments: 'service' is required"], "ERROR_MODEL"),
    (["Arguments were not valid JSON."], "ERROR_MODEL"),
    (["Tool failed: ConnectionError: refused", "Unknown tool 'x'."], "ERROR_INFRA"),
])
def test_invalid_tool_calls_are_a_model_error_not_infra(summaries, outcome):
    t = FakeTranscript(good_diag(), {"escalate": False, "final_confidence": "high"})
    t.tool_calls = [{"result": {"status": "error", "summary": s}} for s in summaries]
    assert eh.score({"service": "payment"}, t)["outcome"] == outcome
