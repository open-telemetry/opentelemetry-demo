"""No tool output may contain flag state, ever. The known flag keys live HERE and nowhere in tools/ or oncall/.

Scans (a) every ledger saved from live runs in tests/fixtures/ledgers/, (b) a deliberately
poisoned recorded trace and log set pushed through the real tools, and (c) fresh output of
the live tools when the backends are reachable (skipped otherwise).
"""
import json
from pathlib import Path

import pytest
import requests

from tests.test_logs import answer, hit
from tests.test_logs import FakeHttp as LogHttp
from tests.test_traces import FakeHttp as TraceHttp
from tests.test_traces import attr, doc, span
from tools.ledger import Ledger
from tools.logs import query_logs
from tools.traces import query_traces

REPO = Path(__file__).resolve().parent.parent
LEDGERS = sorted((REPO / "tests" / "fixtures" / "ledgers").glob("*.json"))

# The flag keys listed in CONTEXT.md section 5, plus the two agent-service flags and the PII one.
FLAG_KEYS = [
    "paymentFailure", "paymentUnreachable", "cartFailure", "productCatalogFailure", "productCatalogLockContention",
    "recommendationCacheFailure", "adFailure", "adHighCpu", "adManualGc", "emailMemoryLeak", "imageSlowLoad",
    "intlShippingSlowdown", "kafkaQueueProblems", "kafkaConsumerDead", "failedReadinessProbe",
    "loadGeneratorFloodHomepage", "cartMetricCardinalityOverflow", "emitRawPii", "aiRunawayAgent", "aiSlowResponse",
]
OTHER_FORBIDDEN = ["feature_flag", "feature flag", "flagd", "flagservice", "openfeature", "/feature/"]


def leaks(text: str) -> list[str]:
    lowered = text.lower()
    return [word for word in FLAG_KEYS + OTHER_FORBIDDEN if word.lower() in lowered]


def test_the_scanner_itself_catches_each_forbidden_word():
    for word in FLAG_KEYS + OTHER_FORBIDDEN:
        assert leaks(f"some output {word} more") == [word] or word in leaks(f"some output {word} more")
    assert leaks('{"service": "cart", "message": "Wasn\'t able to connect to redis"}') == []


def test_there_are_saved_ledgers_to_scan():
    assert LEDGERS, "run `python -m tools.snapshot --save-ledger tests/fixtures/ledgers/<name>.json` during a live run"


@pytest.mark.parametrize("path", LEDGERS, ids=lambda p: p.name)
def test_saved_ledgers_contain_no_flag_data(path):
    assert leaks(path.read_text(encoding="utf-8")) == []


def test_the_sanitiser_and_tools_hold_no_specific_flag_names():
    for path in [*(REPO / "tools").glob("*.py"), *(REPO / "oncall").glob("*.py")]:
        text = path.read_text(encoding="utf-8").lower()
        assert [k for k in FLAG_KEYS if k.lower() in text] == [], path.name


# --- a poisoned recording pushed through the real tools ---------------------------------

def poisoned_trace():
    events = [{"name": "feature_flag.evaluation",
               "attributes": [attr("feature_flag.key", key), attr("feature_flag.provider.name", "flagd"), attr("feature_flag.result.variant", "on")]}
              for key in FLAG_KEYS]
    evaluation = [
        span(f"e{i}", "a", "flagd.evaluation.v2.Service/ResolveBoolean", "cart", 3, 1, 2, {"code": 2, "message": f"{key} failed"},
             scope="OpenTelemetry.Instrumentation.GrpcNetClient", attrs=[attr("rpc.method", "ResolveBoolean")])
        for i, key in enumerate(FLAG_KEYS)
    ]
    real = span("a", None, "GET /cart", "cart", 2, 0, 20, {"code": 2, "message": "cache down: flagd said paymentFailure"},
                attrs=[attr("demo.feature_flag.recommendation_cache", "cartFailure")], events=events)
    return [real, *evaluation, span("z", None, "resolveBoolean", "flagd", 1, 0, 1, {"code": 2, "message": "emitRawPii"}, trace="t1")]


def test_a_poisoned_trace_comes_out_clean_through_query_traces_and_the_ledger():
    result = query_traces(base_url="http://jaeger.test", http_get=TraceHttp(doc(*poisoned_trace())))
    assert result.state == "data" and result.items[0]["span_count"] == 1
    ledger = Ledger()
    ledger.add("query_traces", {"service": None}, result)
    assert leaks(json.dumps([e.result for e in ledger.list()])) == []


def test_poisoned_log_lines_come_out_clean_through_query_logs_and_the_ledger():
    hits = [hit(f"evaluation of {key} failed: flagd said no", service="cart") for key in FLAG_KEYS]
    hits += [hit(f"feature_flag {key} resolved by OpenFeature", service="cart") for key in FLAG_KEYS[:3]]
    hits += [hit("Wasn't able to connect to redis", service="cart", level="error")] * 2
    result = query_logs(base_url="http://os.test", http_post=LogHttp(answer(hits)))
    ledger = Ledger()
    ledger.add("query_logs", {}, result)
    assert [g["message"] for g in result.items] == ["Wasn't able to connect to redis"]
    assert leaks(json.dumps([e.result for e in ledger.list()])) == []


def test_known_limitation_a_bare_flag_key_in_a_log_line_is_not_removed():
    # The sanitiser holds no flag names (by design), so a line that only contains a key name and
    # none of the flag-system words passes through. The live scans above exist to catch that.
    result = query_logs(base_url="http://os.test", http_post=LogHttp(answer([hit("paymentFailure happened", service="payment")])))
    assert leaks(json.dumps(result.items)) == ["paymentFailure"]


# --- fresh output from the live backends ------------------------------------------------

def backends_reachable() -> bool:
    from tools.endpoints import get_endpoints
    endpoints = get_endpoints()
    try:
        return (
            requests.get(f"{endpoints['prometheus'].url}/api/v1/status/buildinfo", timeout=3).ok
            and requests.get(f"{endpoints['jaeger'].url}/api/v3/services", timeout=3).ok
            and endpoints["opensearch"].url is not None
            and requests.get(f"{endpoints['opensearch'].url}/_cluster/health", timeout=3).ok
        )
    except requests.exceptions.RequestException:
        return False


@pytest.mark.live
def test_fresh_output_of_every_tool_has_no_flag_data():
    if not backends_reachable():
        pytest.skip("live backends are not reachable")
    from tools.containers import container_health
    from tools.deploys import deploy_history
    from tools.metrics import query_metrics
    ledger = Ledger()
    for tool, arguments, run in (
        ("container_health", {}, lambda: container_health()),
        ("query_metrics", {}, lambda: query_metrics(window_minutes=5)),
        ("query_traces", {"mode": "errors"}, lambda: query_traces(window_minutes=10, limit=10)),
        ("query_traces", {"mode": "slow"}, lambda: query_traces(window_minutes=10, limit=10, mode="slow")),
        ("query_logs", {}, lambda: query_logs(window_minutes=10, limit=20)),
        ("deploy_history", {}, lambda: deploy_history()),
    ):
        ledger.add(tool, arguments, run())
    assert leaks(json.dumps([e.result for e in ledger.list()])) == []
