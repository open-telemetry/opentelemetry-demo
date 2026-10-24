import json

import pytest
import requests

from oncall import toolbox
from tools.ledger import Ledger
from tools.metrics import PromError, change_line, error_rate_pct, instant_query, parse_vector, query_metrics


def vector(*series):
    return {"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": labels, "value": [1.0, str(value)]} for labels, value in series]}}


class FakePrometheus:
    """Answers query_metrics' queries from canned vectors, chosen by what the PromQL asks for."""

    def __init__(self, calls=(), errors=(), p95=(), spans=(), status=200, base_calls=(), base_errors=(), base_p95=()):
        self.by_kind = {"calls": calls, "errors": errors, "p95": p95, "spans": spans,
                        "base_calls": base_calls, "base_errors": base_errors, "base_p95": base_p95}
        self.status = status

    def kind(self, promql):
        base = "base_" if " offset " in promql else ""
        if "histogram_quantile" in promql:
            return base + "p95"
        if "span_name" in promql:
            return "spans"
        if "traces_span_metrics_calls_total" in promql:
            return base + ("errors" if "STATUS_CODE_ERROR" in promql else "calls")
        return None

    def __call__(self, url, params, timeout):
        kind = self.kind(params["query"])
        response = requests.Response()
        response.status_code = self.status
        response._content = json.dumps(vector(*self.by_kind.get(kind, ()))).encode()
        return response


def svc(name, **extra):
    return {"service_name": name, **extra}


def test_parse_vector_maps_nan_to_none():
    assert parse_vector(vector((svc("a"), "NaN"), (svc("b"), 2))) == [(svc("a"), None), (svc("b"), 2.0)]


def test_parse_vector_rejects_error_status():
    with pytest.raises(ValueError):
        parse_vector({"status": "error", "error": "boom"})


def test_error_rate_is_errors_over_all_calls_not_ok_calls():
    # 2 errors/s out of 10 calls/s of which most are UNSET: 20 %, whatever the OK count is.
    assert error_rate_pct(2.0, 10.0) == 20.0
    assert error_rate_pct(None, 10.0) == 0.0
    assert error_rate_pct(1.0, 0) is None  # no traffic: unknown, not 0 %


def test_query_uses_error_over_all_calls_in_promql():
    fake = FakePrometheus(calls=[(svc("cart"), 10)], p95=[(svc("cart"), 100)])
    result = query_metrics(base_url="http://prom", http_get=fake)
    err_query = next(q for q in result.query if 'status_code="STATUS_CODE_ERROR"' in q)
    all_query = result.query[0]
    assert "STATUS_CODE_OK" not in " ".join(result.query)
    assert "status_code" not in all_query and err_query != all_query


def test_data_state_rates_and_ranking_and_cap():
    calls = [(svc("cart"), 10), (svc("payment"), 5), (svc("ad"), 1), (svc("flagd"), 12)]
    errors = [(svc("cart"), 2), (svc("flagd"), 12)]
    p95 = [(svc("cart"), 30), (svc("payment"), 20), (svc("ad"), 900), (svc("flagd"), 5)]
    spans = [(svc("cart", span_name="POST /cart", span_kind="SPAN_KIND_SERVER"), 1.5),
             (svc("cart", span_name="HGET", span_kind="SPAN_KIND_CLIENT"), 2.0)]
    result = query_metrics(top_n=2, base_url="http://prom", http_get=FakePrometheus(calls, errors, p95, spans))
    assert result.state == "data"
    assert [r["service"] for r in result.items] == ["cart", "ad"]  # worst errors, then worst latency
    cart = result.items[0]
    assert cart["error_rate_pct"] == 20.0 and cart["request_rate_per_s"] == 10.0 and cart["p95_ms"] == 30.0
    assert [s["span_name"] for s in cart["top_error_spans"]] == ["HGET", "POST /cart"]
    assert result.total_items == 3  # flagd dropped before counting
    assert "flagd" not in str(result.to_dict())


def test_no_data_when_prometheus_has_no_series():
    result = query_metrics(base_url="http://prom", http_get=FakePrometheus())
    assert result.state == "no_data" and result.items == [] and "NOT a healthy signal" in result.notes[0]


def test_backend_error_on_http_error_status():
    result = query_metrics(base_url="http://prom", http_get=FakePrometheus(status=503))
    assert result.state == "backend_error" and "503" in result.error and result.items == []


def test_backend_error_on_closed_port():
    result = query_metrics(base_url="http://127.0.0.1:1")
    assert result.state == "backend_error" and "unreachable" in result.error


def test_instant_query_raises_on_garbage_body():
    class Garbage:
        ok, status_code, text = True, 200, "<html>"
        def json(self):
            raise ValueError("not json")
    with pytest.raises(PromError):
        instant_query("http://prom", "up", 0, lambda *a, **k: Garbage())


@pytest.mark.parametrize("kwargs", [{"window_minutes": 1}, {"window_minutes": 0}, {"top_n": 0}, {"service": 'a"} or vector(1) #'}])
def test_bad_arguments_are_rejected_before_any_query(kwargs):
    with pytest.raises(ValueError):
        query_metrics(base_url="http://prom", **kwargs)


def test_top_error_spans_cover_all_kinds_and_drop_flag_rows():
    spans = [
        (svc("load-generator", span_name="POST", span_kind="SPAN_KIND_CLIENT"), 0.13),
        (svc("ad", span_name="flagd.evaluation.v2.Service/EventStream", span_kind="SPAN_KIND_CLIENT"), 0.5),
        (svc("flagd", span_name="Resolve", span_kind="SPAN_KIND_SERVER"), 0.9),
        (svc("cart", span_name="HGET", span_kind="SPAN_KIND_CLIENT"), 0.0),
    ]
    result = query_metrics(base_url="http://prom", http_get=FakePrometheus(calls=[(svc("cart"), 1)], spans=spans))
    assert result.extra["top_error_spans"] == [
        {"service": "load-generator", "span_name": "POST", "span_kind": "client", "error_rate_per_s": 0.13}
    ]


# --- baseline comparison ------------------------------------------------------------------

def rows_by_service(result):
    return {r["service"]: r for r in result.items}


def test_change_line_has_one_fixed_format():
    before = {"request_rate_per_s": 4.1, "error_rate_pct": 0.2, "p95_ms": 120.0}
    now = {"request_rate_per_s": 3.9, "error_rate_pct": 38.0, "p95_ms": 3950.0}
    assert change_line(now, before) == "errors 0.20% -> 38.00%; p95 120 ms -> 3950 ms; rate 4.10/s -> 3.90/s"
    assert change_line({**now, "p95_ms": None}, {**before, "p95_ms": 2.34}).startswith("errors 0.20% -> 38.00%; p95 2.3 ms -> n/a;")


def test_query_adds_baseline_queries_that_end_where_the_window_starts():
    fake = FakePrometheus(calls=[(svc("cart"), 4)])
    result = query_metrics(window_minutes=7, base_url="http://prom", http_get=fake)
    baseline = [q for q in result.query if " offset " in q]
    assert len(baseline) == 3 and all("[30m] offset 7m)" in q for q in baseline)
    assert result.extra["baseline_window"]["minutes"] == 30
    assert result.extra["baseline_window"]["end"] == result.window["start"]


def test_change_line_per_service_from_recent_and_baseline():
    fake = FakePrometheus(
        calls=[(svc("cart"), 3.9)], errors=[(svc("cart"), 1.482)], p95=[(svc("cart"), 3950)],
        base_calls=[(svc("cart"), 4.1)], base_errors=[(svc("cart"), 0.0082)], base_p95=[(svc("cart"), 120)],
    )
    cart = rows_by_service(query_metrics(base_url="http://prom", http_get=fake))["cart"]
    assert cart["change"] == "errors 0.20% -> 38.00%; p95 120 ms -> 3950 ms; rate 4.10/s -> 3.90/s"
    assert cart["baseline"]["error_rate_pct"] == 0.2


def test_baseline_without_data_says_so():
    result = query_metrics(base_url="http://prom", http_get=FakePrometheus(calls=[(svc("cart"), 2)], p95=[(svc("cart"), 50)]))
    assert result.state == "data" and result.items[0]["change"] == "baseline n/a" and result.items[0]["baseline"] is None


def test_service_with_traffic_before_and_none_now_is_absent():
    fake = FakePrometheus(calls=[(svc("cart"), 5)], base_calls=[(svc("cart"), 5), (svc("payment"), 4.1)],
                          base_p95=[(svc("payment"), 80)])
    result = query_metrics(base_url="http://prom", http_get=fake)
    payment = rows_by_service(result)["payment"]
    assert result.state == "data" and payment["change"] == "absent now (was 4.10/s)" and payment["request_rate_per_s"] == 0.0
    fake = FakePrometheus(calls=[(svc("payment"), 0)], base_calls=[(svc("payment"), 4.1)])  # series still there, rate fell to 0
    assert query_metrics(base_url="http://prom", http_get=fake).items[0]["change"] == "absent now (was 4.10/s)"


def test_baseline_only_is_still_not_a_healthy_no_data_when_both_periods_are_empty():
    assert query_metrics(base_url="http://prom", http_get=FakePrometheus()).state == "no_data"


def test_services_are_ranked_by_how_much_they_got_worse():
    fake = FakePrometheus(
        calls=[(svc("steady"), 5), (svc("noisy"), 5), (svc("broken"), 5), (svc("slow"), 5), (svc("quiet"), 1)],
        errors=[(svc("noisy"), 1.0), (svc("broken"), 2.5)],  # noisy 20 % (was 20 %), broken 50 % (was 0 %)
        p95=[(svc("steady"), 100), (svc("noisy"), 100), (svc("broken"), 100), (svc("slow"), 4000), (svc("quiet"), 10)],
        base_calls=[(svc("steady"), 5), (svc("noisy"), 5), (svc("broken"), 5), (svc("slow"), 5), (svc("quiet"), 1), (svc("gone"), 3)],
        base_errors=[(svc("noisy"), 1.0)],
        base_p95=[(svc("steady"), 100), (svc("noisy"), 100), (svc("broken"), 100), (svc("slow"), 100), (svc("quiet"), 10)],
    )
    result = query_metrics(top_n=10, base_url="http://prom", http_get=fake)
    assert [r["service"] for r in result.items] == ["broken", "slow", "gone", "noisy", "steady", "quiet"]


def test_cap_still_surfaces_a_latency_rise_and_an_absent_service():
    fake = FakePrometheus(
        calls=[(svc("a"), 5), (svc("b"), 5), (svc("slow"), 5)],
        errors=[(svc("a"), 0.5), (svc("b"), 0.25)],
        p95=[(svc("slow"), 3000)],
        base_calls=[(svc("a"), 5), (svc("b"), 5), (svc("slow"), 5), (svc("gone"), 2)], base_p95=[(svc("slow"), 100)],
    )
    names = [r["service"] for r in query_metrics(top_n=3, base_url="http://prom", http_get=fake).items]
    assert set(names) == {"a", "slow", "gone"}


def test_baseline_services_from_the_flag_service_are_dropped():
    fake = FakePrometheus(calls=[(svc("cart"), 1)], base_calls=[(svc("cart"), 1), (svc("flagd"), 9)])
    assert "flagd" not in str(query_metrics(base_url="http://prom", http_get=fake).to_dict())


def test_backend_error_when_only_the_baseline_query_fails():
    def fails_on_offset(url, params, timeout):
        if " offset " in params["query"]:
            raise requests.exceptions.ConnectionError("down")
        return FakePrometheus(calls=[(svc("cart"), 1)])(url, params, timeout)
    result = query_metrics(base_url="http://prom", http_get=fails_on_offset)
    assert result.state == "backend_error" and "unreachable" in result.error and result.items == []


def test_the_change_string_in_the_compact_view_is_the_one_in_the_ledger_entry():
    fake = FakePrometheus(
        calls=[(svc("cart"), 3.9), (svc("ad"), 2)], errors=[(svc("cart"), 1.482)], p95=[(svc("cart"), 3950), (svc("ad"), 30)],
        base_calls=[(svc("cart"), 4.1), (svc("payment"), 4.1)], base_errors=[(svc("cart"), 0.0082)], base_p95=[(svc("cart"), 120)],
    )
    ledger = Ledger()
    entry = ledger.add("query_metrics", {"window_minutes": 5}, query_metrics(base_url="http://prom", http_get=fake))
    view = toolbox.compact_view(entry)
    in_view = {s["service"]: s["change"] for s in view["services"]}
    in_ledger = {r["service"]: r["change"] for r in entry.result["items"]}
    assert in_view == in_ledger and set(in_view) == {"cart", "ad", "payment"}
    assert in_view["cart"] == "errors 0.20% -> 38.00%; p95 120 ms -> 3950 ms; rate 4.10/s -> 3.90/s"
    assert view["baseline_window"] == entry.result["extra"]["baseline_window"]
    assert all(change in toolbox.view_text(view) for change in in_ledger.values())  # verbatim, as the model reads it
