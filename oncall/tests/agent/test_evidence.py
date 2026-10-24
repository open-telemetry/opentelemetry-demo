import pytest

from oncall.agent.evidence import salvage, service_of, validate
from oncall.agent.runlog import RunLog
from oncall.models import make_result

# Copied from run 20261023_194644_0869ab: the model glued the text onto the id.
REAL_MALFORMED = (
    "container:product-catalog: product-catalog: state=running, health=healthy, "
    "restarts=0, exit_code=0, oom_killed=false, "
    "started_at=2026-10-23T10:04:39.741734367Z, cpu=163.4% of one core, "
    "mem=70.3% of limit"
)
M_CART = "metric:error_rate:cart@2026-10-23T19:00:00+00:00"
M_CHECKOUT = "metric:error_rate:checkout@2026-10-23T19:00:00+00:00"
LOG_CART = "log:cart:1@2026-10-23T19:00:01Z"
TRACE_CART = "trace:abc/span:GetCart"


def _ev(eid, text):
    return {"id": eid, "text": text, "ts": None}


@pytest.fixture
def run(tmp_path):
    r = RunLog(run_id="ev", runs_dir=str(tmp_path))
    r.log(
        "tool_result",
        name="get_metrics",
        result=make_result(
            "get_metrics",
            {},
            "",
            [
                _ev(M_CART, "cart error_rate 0.3100 (baseline 0.0100, delta +0.3000)"),
                _ev(
                    M_CHECKOUT,
                    "checkout error_rate 0.0200 (baseline 0.0100, delta +0.0100)",
                ),
            ],
        ),
    )
    r.log(
        "tool_result",
        name="container_health",
        result=make_result(
            "container_health",
            {},
            "",
            [
                _ev("container:product-catalog", "product-catalog: state=running"),
                _ev(
                    "container:product-catalog-db", "product-catalog-db: state=running"
                ),
            ],
        ),
    )
    r.log(
        "tool_result",
        name="search_logs",
        result=make_result("search_logs", {}, "", [_ev(LOG_CART, "x3 [cart] boom")]),
    )
    r.log(
        "tool_result",
        name="search_traces",
        result=make_result(
            "search_traces", {}, "", [_ev(TRACE_CART, "cart ERROR redis down")]
        ),
    )
    return r


def _diagnosis(**over):
    d = {
        "component": "cart",
        "category": "dependency_unavailable",
        "cause": "cart cannot reach its cache",
        "confidence": 0.9,
        "evidence_ids": [M_CART, TRACE_CART, LOG_CART],
        "affected_services": ["cart"],
        "alternatives": [],
        "decision": "act",
        "reasoning": f"cart errors at 0.31 [{M_CART}]. Traces show redis down [{TRACE_CART}].",
    }
    d.update(over)
    return d


def test_valid_diagnosis_passes_unchanged(run):
    d, problems = validate(_diagnosis(), run)
    assert problems == []
    assert d["confidence"] == 0.9
    assert d["evidence_ids"] == [M_CART, TRACE_CART, LOG_CART]


def test_fabricated_trace_id_removed(run):
    fake = "trace:deadbeef/span:Charge"
    d, problems = validate(
        _diagnosis(
            evidence_ids=[M_CART, fake, LOG_CART],
            reasoning=f"Payment declined [{fake}]. cart errors at 0.31 [{M_CART}].",
        ),
        run,
    )
    assert fake not in d["evidence_ids"]
    assert fake not in d["reasoning"]
    assert d["reasoning"] == f"cart errors at 0.31 [{M_CART}]."
    assert any("not in run log" in p for p in problems)
    assert any("unknown ids" in p for p in problems)


def test_real_malformed_id_salvaged_to_its_one_prefix(run):
    index = run.evidence_index()
    # "container:product-catalog-db" is not a prefix of it, so exactly one match.
    assert salvage(REAL_MALFORMED, index) == "container:product-catalog"
    d, problems = validate(_diagnosis(evidence_ids=[REAL_MALFORMED, M_CART]), run)
    assert d["evidence_ids"] == ["container:product-catalog", M_CART]
    assert any("repaired malformed evidence id" in p for p in problems)


def test_malformed_id_with_two_prefixes_is_dropped(run):
    ambiguous = "container:product-catalog-db: text"
    # Both "container:product-catalog" and "container:product-catalog-db" prefix it.
    assert salvage(ambiguous, run.evidence_index()) is None
    d, problems = validate(_diagnosis(evidence_ids=[ambiguous, M_CART]), run)
    assert d["evidence_ids"] == [M_CART]
    assert any("dropped evidence id" in p for p in problems)


def test_wrong_metric_value_flagged(run):
    _d, problems = validate(
        _diagnosis(reasoning=f"cart error rate reached 0.75 [{M_CART}]."), run
    )
    assert any("do not match" in p for p in problems)
    _ok, ok_problems = validate(
        _diagnosis(reasoning=f"cart error rate is 31% [{M_CART}]."), run
    )
    assert not any("do not match" in p for p in ok_problems)


def test_zero_evidence_escalates_unknown(run):
    d, _problems = validate(_diagnosis(evidence_ids=["log:nope@1"]), run)
    assert d["evidence_ids"] == []
    assert (d["decision"], d["category"], d["component"]) == (
        "escalate",
        "unknown",
        None,
    )


def test_thin_evidence_lowers_confidence(run):
    d, problems = validate(_diagnosis(evidence_ids=[M_CART]), run)
    assert d["confidence"] == pytest.approx(0.54)
    assert any("thin evidence" in p for p in problems)


def test_service_of_each_id_kind(run):
    index = run.evidence_index()
    assert service_of(index[M_CART]) == "cart"
    assert service_of(index[LOG_CART]) == "cart"
    assert service_of(index[TRACE_CART]) == "cart"
    assert service_of(index["container:product-catalog"]) == "product-catalog"
    assert service_of(_ev("metric:top_errors:cart/GetCart@t", "")) == "cart"
