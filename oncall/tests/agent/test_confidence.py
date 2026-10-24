import pytest

from oncall.agent.confidence import assess, collect
from oncall.agent.runlog import RunLog
from oncall.models import make_result

TS = "@2026-10-23T20:00:00+00:00"


def _ev(eid, text):
    return {"id": eid, "text": text, "ts": None}


def _metric(service, metric, now, base):
    comparison = (
        "baseline unavailable" if base is None else f"baseline {base}, delta +0"
    )
    return _ev(
        f"metric:{metric}:{service}{TS}", f"{service} {metric} {now} ({comparison})"
    )


def _container(name, flagged="", usage="cpu=5.0% of one core, mem=40.0% of limit"):
    text = f"{name}: state=running, health=none, restarts=0, exit_code=0, {usage}"
    if flagged:
        text += f" | FLAGGED: {flagged}"
    return _ev(f"container:{name}", text)


class Run:
    def __init__(self, tmp_path):
        self.log = RunLog(run_id="c", runs_dir=str(tmp_path))

    def metrics(self, metric, *evidence, service=None):
        query = {"metric": metric, "service": service}
        self.log.log(
            "tool_result",
            name="get_metrics",
            result=make_result("get_metrics", query, "", list(evidence)),
        )
        return self

    def containers(self, *evidence, service=None):
        self.log.log(
            "tool_result",
            name="container_health",
            result=make_result(
                "container_health", {"service": service}, "", list(evidence)
            ),
        )
        return self

    def traces(self, *evidence):
        self.log.log(
            "tool_result",
            name="search_traces",
            result=make_result("search_traces", {}, "", list(evidence)),
        )
        return self


@pytest.fixture
def run(tmp_path):
    return Run(tmp_path)


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_MIN", "0.7")
    monkeypatch.setenv("ALERT_ERROR_RATE", "0.05")
    monkeypatch.setenv("ALERT_P95_MS", "1000")


def _d(**over):
    d = {
        "component": "payment",
        "category": "app_error",
        "cause": "payment charge fails",
        "confidence": 0.9,
        "evidence_ids": [],
        "affected_services": ["payment", "checkout"],
        "alternatives": [{"hypothesis": "network", "rejected_because": "no timeouts"}],
        "decision": "act",
        "reasoning": "payment errors",
    }
    d.update(over)
    return d


def _healthy(run):
    return (
        run.metrics("error_rate", _metric("cart", "error_rate", 0.0, 0.0))
        .metrics("latency_p95", _metric("checkout", "latency_p95", 900.0, 850.0))
        .containers(
            _container(
                "product-catalog", usage="cpu=163.4% of one core, mem=70.3% of limit"
            ),
            _container("cart"),
        )
    )


def _payment_incident(run):
    m = _metric("payment", "error_rate", 0.4, 0.01)
    t = _ev("trace:abc/span:Charge", "payment ERROR card declined")
    run.metrics("error_rate", m).containers(_container("payment")).traces(t)
    return [m["id"], t["id"]]


def test_clear_single_service_case_stays_act(run):
    ids = _payment_incident(run)
    d = assess(_d(evidence_ids=ids), run.log)
    assert (d["decision"], d["confidence"]) == ("act", 0.9)


def test_healthy_baseline_false_positive_becomes_no_incident(run):
    _healthy(run)
    cpu = "container:product-catalog"
    d = assess(
        _d(
            component="product-catalog",
            category="resource_cpu",
            confidence=0.7,
            evidence_ids=[cpu],
        ),
        run.log,
    )
    assert (d["category"], d["decision"], d["component"]) == (
        "no_incident",
        "no_action",
        None,
    )
    assert d["confidence"] == 0.85
    assert "no regression in any service" in d["reasoning"]


def test_healthy_without_baselines_is_less_sure(run):
    run.metrics("error_rate", _metric("cart", "error_rate", 0.01, None)).containers(
        _container("cart")
    )
    d = assess(_d(), run.log)
    assert d["decision"] == "no_action"
    assert d["confidence"] == pytest.approx(0.35)


def test_act_requires_a_regression_for_the_component(run):
    ids = _payment_incident(run)
    t = _ev("trace:def/span:Ship", "shipping ERROR slow")
    run.traces(t)
    d = assess(_d(component="shipping", evidence_ids=[*ids, t["id"]]), run.log)
    assert d["decision"] == "escalate"
    assert "no regression signal for shipping" in d["reasoning"]


def test_cpu_without_limit_is_not_evidence(run):
    m = _metric("ad", "latency_p95", 3000.0, 900.0)
    c = _container("ad", usage="cpu=180.0% of one core, mem=40.0% of limit")
    run.metrics("latency_p95", m).containers(c)
    d = assess(
        _d(component="ad", category="resource_cpu", evidence_ids=[m["id"], c["id"]]),
        run.log,
    )
    assert d["confidence"] <= 0.3 and d["decision"] == "escalate"
    assert "no cpu limit hit or rise for ad" in d["reasoning"]


def test_cpu_limit_hit_supports_resource_cpu(run):
    m = _metric("ad", "latency_p95", 3000.0, 900.0)
    c = _container(
        "ad", "CPU 98% of limit", usage="cpu=98.0% of limit, mem=40.0% of limit"
    )
    t = _ev("trace:x/span:GetAds", "ad ERROR deadline exceeded")
    run.metrics("latency_p95", m).containers(c).traces(t)
    d = assess(
        _d(
            component="ad",
            category="resource_cpu",
            evidence_ids=[m["id"], c["id"], t["id"]],
        ),
        run.log,
    )
    assert d["decision"] == "act"


def test_missing_baseline_cannot_support_act(run):
    m = _metric("payment", "error_rate", 0.4, None)
    t = _ev("trace:abc/span:Charge", "payment ERROR declined")
    run.metrics("error_rate", m, _metric("cart", "error_rate", 0.3, 0.01)).traces(t)
    d = assess(_d(evidence_ids=[m["id"], t["id"]]), run.log)
    assert d["confidence"] == 0.5 and d["decision"] == "escalate"


def test_container_down_with_matching_trace_gets_bonus(run):
    c = _container("valkey-cart", "not running (state=exited, exit_code=0)")
    t = _ev("trace:abc/span:GetCart", "valkey-cart ERROR connection refused")
    run.metrics("error_rate", _metric("cart", "error_rate", 0.0, 0.0)).containers(
        c
    ).traces(t)
    d = assess(
        _d(
            component="valkey-cart",
            category="dependency_unavailable",
            confidence=0.8,
            evidence_ids=[c["id"], t["id"]],
        ),
        run.log,
    )
    assert (d["decision"], d["confidence"]) == ("act", 0.9)


def test_two_unhealthy_containers_cap(run):
    a = _container("email", "not running (state=exited, exit_code=0)")
    b = _container("quote", "OOM-killed")
    t = _ev("trace:abc/span:Send", "email ERROR unavailable")
    run.metrics("error_rate").containers(a, b).traces(t)
    d = assess(
        _d(
            component="email",
            category="container_down",
            evidence_ids=[a["id"], t["id"]],
        ),
        run.log,
    )
    assert d["confidence"] == 0.5 and d["decision"] == "escalate"


def test_client_or_missing_component_escalates(run):
    ids = _payment_incident(run)
    assert (
        assess(_d(component=None, evidence_ids=ids), run.log)["decision"] == "escalate"
    )


def test_unknown_category_and_no_alternatives(run):
    ids = _payment_incident(run)
    d = assess(_d(category="unknown", alternatives=[], evidence_ids=ids), run.log)
    assert d["confidence"] == pytest.approx(0.2)


def test_claimed_no_incident_with_regressions_is_overridden(run):
    ids = _payment_incident(run)
    d = assess(
        _d(
            component=None,
            category="no_incident",
            decision="no_action",
            evidence_ids=ids,
        ),
        run.log,
    )
    assert d["category"] == "unknown" and d["decision"] == "escalate"


def test_collect_reads_regressions_and_faults(run):
    _payment_incident(run)
    run.containers(_container("email", "not running (state=exited, exit_code=0)"))
    s = collect(run.log)
    assert set(s.regressions) == {"payment"}
    assert s.container_faults == {"email": ["not running"]}
    assert s.unhealthy() == {"payment", "email"}


def test_no_healthy_claim_without_all_container_triage(run):
    m = _metric("cart", "error_rate", 0.0027, 0.0)
    t = _ev("trace:abc/span:GetCart", "cart ERROR cannot connect to cache")
    run.metrics("error_rate", m).containers(
        _container("frontend-proxy"), service="frontend-proxy"
    ).traces(t)
    d = assess(
        _d(
            component="cart",
            category="dependency_unavailable",
            evidence_ids=[m["id"], t["id"]],
        ),
        run.log,
    )
    assert d["category"] != "no_incident" and d["decision"] == "escalate"
    assert d["confidence"] <= 0.4
    assert "triage incomplete" in d["reasoning"]
    claimed = assess(
        _d(
            component=None,
            category="no_incident",
            decision="no_action",
            evidence_ids=[m["id"]],
        ),
        run.log,
    )
    assert (claimed["category"], claimed["decision"]) == ("unknown", "escalate")
