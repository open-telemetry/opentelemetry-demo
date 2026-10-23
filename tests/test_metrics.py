import json

import pytest
import requests

from tools.metrics import PromError, error_rate_pct, instant_query, parse_vector, query_metrics


def vector(*series):
    return {"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": labels, "value": [1.0, str(value)]} for labels, value in series]}}


class FakePrometheus:
    """Answers query_metrics' queries from canned vectors, chosen by what the PromQL asks for."""

    def __init__(self, calls=(), errors=(), p95=(), spans=(), status=200):
        self.by_kind = {"calls": calls, "errors": errors, "p95": p95, "spans": spans}
        self.status = status

    def kind(self, promql):
        if "histogram_quantile" in promql:
            return "p95"
        if "span_name" in promql:
            return "spans"
        if "traces_span_metrics_calls_total" in promql:
            return "errors" if "STATUS_CODE_ERROR" in promql else "calls"
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
