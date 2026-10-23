import json

import pytest
import requests

from tools import sanitize
from tools.traces import (
    JaegerError, error_signals, fetch, flatten, parse_blocks, pick_diverse, query_traces, summarise,
)

# Shapes copied from live Jaeger v3 responses: ids are hex strings, times are nanosecond strings,
# kind is an int, an UNSET status is {}, an ERROR status is {"code": 2, "message": ...}.
T0 = 1792778219000000000


def attr(key, value):
    kind = "intValue" if isinstance(value, int) else "stringValue"
    return {"key": key, "value": {kind: str(value) if kind == "intValue" else value}}


def span(span_id, parent, name, service="cart", kind=2, start=0, end=10, status=None, attrs=(), events=(), scope="scope", trace="t1"):
    return {
        "service": service, "scope": scope,
        "raw": {
            "traceId": trace, "spanId": span_id, **({"parentSpanId": parent} if parent else {}),
            "name": name, "kind": kind,
            "startTimeUnixNano": str(T0 + start * 1_000_000), "endTimeUnixNano": str(T0 + end * 1_000_000),
            "attributes": list(attrs), "events": list(events), **({"status": status} if status else {"status": {}}),
        },
    }


def blocks(*spans):
    """Group spans into resourceSpans blocks the way Jaeger does: one block per (service, scope)."""
    grouped: dict = {}
    for s in spans:
        grouped.setdefault((s["service"], s["scope"]), []).append(s["raw"])
    return [
        {"resource": {"attributes": [attr("service.name", service)]},
         "scopeSpans": [{"scope": {"name": scope}, "spans": raw}]}
        for (service, scope), raw in grouped.items()
    ]


def doc(*spans):
    return json.dumps({"result": {"resourceSpans": blocks(*spans)}})


EXCEPTION = {"name": "exception", "attributes": [attr("exception.type", "Boom"), attr("exception.message", "it broke")]}

# A checkout that fails because payment fails: the payment span is the deepest erroring one.
PAYMENT_TRACE = [
    span("a", None, "POST /api/checkout", "frontend", 2, 0, 100, {"code": 2}),
    span("b", "a", "PlaceOrder", "checkout", 2, 5, 95, {"code": 2, "message": "failed to charge"}),
    span("c", "b", "Charge", "checkout", 3, 10, 90, {"code": 2, "message": "Payment request failed"}),
    span("d", "c", "Charge", "payment", 2, 12, 88, {"code": 2, "message": "Payment request failed"}),
    span("e", "d", "charge", "payment", 1, 14, 80, {"code": 2, "message": "Payment request failed"}, events=[EXCEPTION]),
    span("f", "a", "GetCart", "cart", 3, 1, 4),
]


def summary_of(spans, trace="t1"):
    flat = flatten(blocks(*spans))
    kept, _ = sanitize.clean_spans(flat[trace])
    return summarise(trace, kept)


# --- parsing --------------------------------------------------------------------------

def test_parse_blocks_reads_one_or_several_concatenated_documents():
    one = doc(span("a", None, "x"))
    assert len(parse_blocks(one)) == 1
    assert len(parse_blocks(one + "\n" + doc(span("b", None, "y", "payment")))) == 2


def test_parse_blocks_rejects_garbage_and_error_bodies():
    with pytest.raises(ValueError):
        parse_blocks("<html>nope</html>")
    with pytest.raises(ValueError):
        parse_blocks(json.dumps({"error": {"httpCode": 500, "message": "boom"}}))


def test_flatten_groups_spans_of_one_trace_across_blocks():
    traces = flatten(blocks(span("a", None, "x", "cart"), span("b", "a", "y", "payment")))
    assert list(traces) == ["t1"] and {s["service"] for s in traces["t1"]} == {"cart", "payment"}
    assert traces["t1"][0]["kind"] in {"server", "client"}


# --- what counts as an error ----------------------------------------------------------

def flat(**kw):
    return flatten(blocks(span("a", None, "x", **kw)))["t1"][0]


def test_status_error_is_an_error():
    assert error_signals(flat(status={"code": 2})) == ["status_error"]


def test_unset_status_with_an_exception_event_is_still_an_error():
    # The case seen in P3: the failure is real but the server span is left UNSET.
    why = error_signals(flat(events=[EXCEPTION]))
    assert why == ["exception_event(Boom)"]


def test_error_attribute_and_error_type_count():
    assert "error_attribute" in error_signals(flat(attrs=[attr("error", "true")]))
    assert "error.type=timeout" in error_signals(flat(attrs=[attr("error.type", "timeout")]))


def test_non_ok_rpc_status_counts_in_both_spellings_but_ok_does_not():
    assert error_signals(flat(attrs=[attr("rpc.grpc.status_code", 14)])) == ["rpc_status=14"]
    assert error_signals(flat(attrs=[attr("rpc.response.status_code", "UNAVAILABLE")])) == ["rpc_status=UNAVAILABLE"]
    assert error_signals(flat(attrs=[attr("rpc.grpc.status_code", 0)])) == []
    assert error_signals(flat(attrs=[attr("rpc.response.status_code", "OK")])) == []


def test_http_5xx_counts_but_4xx_and_2xx_do_not():
    assert error_signals(flat(attrs=[attr("http.response.status_code", 503)])) == ["http_status=503"]
    assert error_signals(flat(attrs=[attr("http.response.status_code", 404)])) == []
    assert error_signals(flat(attrs=[attr("http.status_code", 200)])) == []


def test_ok_and_unset_spans_without_signals_are_fine():
    assert error_signals(flat(status={"code": 1})) == []
    assert error_signals(flat()) == []


# --- trace summary --------------------------------------------------------------------

def test_summary_finds_the_deepest_erroring_span():
    s = summary_of(PAYMENT_TRACE)
    assert s["trace_id"] == "t1" and s["span_count"] == 6
    assert s["root_service"] == "frontend" and s["root_operation"] == "POST /api/checkout"
    assert s["duration_ms"] == 100.0
    assert s["error_span_count"] == 5
    assert (s["deepest_error"]["service"], s["deepest_error"]["span"]) == ("payment", "charge")
    assert s["deepest_error"]["message"] == "Payment request failed"
    assert [e["service"] for e in s["error_spans"]][:3] == ["frontend", "checkout", "checkout"]


def test_deepest_error_can_be_a_span_that_is_only_unmarked():
    # A client span with a non-OK RPC status and no ERROR status is the only failure signal in this trace.
    spans = [
        span("a", None, "GET /cart", "frontend-proxy", 2, 0, 50, {"code": 2}),
        span("b", "a", "GetCart", "cart", 2, 2, 40),
        span("c", "b", "HGET", "cart", 3, 4, 30, attrs=[attr("rpc.grpc.status_code", 14)]),
    ]
    s = summary_of(spans)
    assert (s["deepest_error"]["service"], s["deepest_error"]["span"]) == ("cart", "HGET")
    assert s["deepest_error"]["why"] == ["rpc_status=14"]


def test_a_trace_without_errors_has_no_deepest_error():
    s = summary_of([span("a", None, "GET /", "frontend", 2, 0, 5), span("b", "a", "x", "cart", 2, 1, 2)])
    assert s["error_span_count"] == 0 and s["deepest_error"] is None and s["error_spans"] == []


def test_duration_is_the_longest_span_so_a_skewed_clock_cannot_stretch_it():
    spans = [span("a", None, "root", "frontend", 2, 0, 20), span("b", "a", "skewed", "quote", 2, 736_000, 736_001)]
    assert summary_of(spans)["duration_ms"] == 20.0


def test_error_spans_are_capped_but_counted():
    spans = [span("r", None, "root", "frontend", 2, 0, 100, {"code": 2})]
    spans += [span(f"s{i}", "r", f"op{i}", "cart", 3, i, i + 1, {"code": 2}) for i in range(12)]
    s = summary_of(spans)
    assert s["error_span_count"] == 13 and len(s["error_spans"]) == 6


def test_a_span_whose_parent_was_filtered_becomes_a_root_instead_of_crashing():
    spans = [
        span("a", None, "evaluate", "cart", 3, 0, 5, scope="grpc", attrs=[attr("server.address", "flagd")]),
        span("b", "a", "child", "cart", 2, 1, 2, {"code": 2}),
    ]
    s = summary_of(spans)
    assert s["span_count"] == 1 and s["root_operation"] == "child"


def test_pick_diverse_shows_each_failure_kind_before_repeating_one():
    def trace(tid, start, service, span_name):
        return {"trace_id": tid, "start": start, "deepest_error": {"service": service, "span": span_name, "kind": "client"}}
    noisy = [trace(f"n{i}", f"2026-10-23T10:00:{i:02d}", "loadgen", "POST") for i in range(6)]
    rare = [trace("p1", "2026-10-23T09:00:00", "payment", "charge")]
    picked = pick_diverse(noisy + rare, 3)
    assert [t["trace_id"] for t in picked] == ["n5", "p1", "n4"]


# --- the tool: states -----------------------------------------------------------------

class FakeHttp:
    def __init__(self, text="", status=200, raises=None):
        self.text, self.status, self.raises, self.calls = text, status, raises, []

    def __call__(self, url, params, timeout):
        self.calls.append((url, params))
        if self.raises:
            raise self.raises
        response = requests.Response()
        response.status_code = self.status
        response._content = self.text.encode()
        return response


def run(http, **kw):
    return query_traces(base_url="http://jaeger.test", http_get=http, **kw)


def test_data_with_the_exact_query_and_window_recorded():
    http = FakeHttp(doc(*PAYMENT_TRACE))
    result = run(http, service="payment", window_minutes=10, limit=3)
    assert result.state == "data" and result.items[0]["trace_id"] == "t1"
    assert result.window["minutes"] == 10
    assert any("query.service_name=payment" in q for q in result.query)
    assert any("query.attributes" in q for q in result.query)  # the ERROR-only search
    assert len(http.calls) == 2 and http.calls[0][0].endswith("/api/v3/traces")
    assert http.calls[0][1]["query.search_depth"] >= 40
    assert any("items removed by sanitiser" in n for n in result.notes)


def test_no_traces_found_404_is_no_data_not_an_error():
    body = json.dumps({"error": {"httpCode": 404, "message": "No traces found"}})
    result = run(FakeHttp(body, status=404))
    assert result.state == "no_data" and result.items == []
    assert any("NOT a healthy signal" in n for n in result.notes)


def test_traces_without_errors_in_errors_mode_is_no_data():
    healthy = [span("a", None, "GET /", "frontend", 2, 0, 5)]
    assert run(FakeHttp(doc(*healthy))).state == "no_data"


@pytest.mark.parametrize("http", [
    FakeHttp("page not found", status=404),  # the classic route that does not exist
    FakeHttp("boom", status=500),
    FakeHttp("<html>", status=200),
    FakeHttp(raises=requests.exceptions.ConnectionError("refused")),
    FakeHttp(raises=requests.exceptions.ReadTimeout("slow")),
])
def test_backend_problems_are_backend_error_never_no_data(http):
    result = run(http)
    assert result.state == "backend_error" and result.error and result.items == []


def test_slow_mode_ranks_by_duration_and_runs_one_search():
    quick = [span("a", None, "quick", "frontend", 2, 0, 5, trace="q")]
    slow = [span("b", None, "slow", "frontend", 2, 0, 900, trace="s")]
    http = FakeHttp(doc(*quick, *slow))
    result = run(http, mode="slow", limit=2)
    assert [t["trace_id"] for t in result.items] == ["s", "q"] and len(http.calls) == 1


def test_the_flag_service_as_a_filter_is_refused_without_calling_the_backend():
    http = FakeHttp("{}")
    result = run(http, service="flagd")
    assert result.state == "no_data" and http.calls == []


def test_bad_arguments_raise():
    for kw in ({"mode": "x"}, {"window_minutes": 0}, {"window_minutes": 999}, {"limit": 0}, {"service": "a b"}):
        with pytest.raises(ValueError):
            run(FakeHttp("{}"), **kw)


def test_flag_evaluation_spans_never_reach_the_output():
    evaluation = span("x", "a", "flagd.evaluation.v2.Service/ResolveBoolean", "cart", 3, 1, 2, {"code": 2, "message": "flagd down"},
                      scope="OpenTelemetry.Instrumentation.GrpcNetClient")
    http_leg = span("y", "x", "POST", "cart", 3, 1, 2, {"code": 2},
                    attrs=[attr("server.address", "flagd"), attr("url.full", "http://flagd:8013/flagd.evaluation.v2.Service/ResolveBoolean")],
                    scope="System.Net.Http")
    real = span("a", None, "GET /cart", "cart", 2, 0, 20, {"code": 2, "message": "cache down"},
                events=[{"name": "feature_flag.evaluation", "attributes": [attr("feature_flag.key", "someFlag")]}])
    result = run(FakeHttp(doc(real, evaluation, http_leg)))
    text = json.dumps(result.to_dict())
    assert result.state == "data" and result.items[0]["span_count"] == 1
    for banned in ("flagd", "feature_flag", "someFlag", "ResolveBoolean"):
        assert banned not in text


def test_fetch_returns_empty_list_for_no_traces():
    body = json.dumps({"error": {"httpCode": 404, "message": "No traces found"}})
    assert fetch("http://x", {}, FakeHttp(body, status=404)) == []
    with pytest.raises(JaegerError):
        fetch("http://x", {}, FakeHttp("nope", status=404))
