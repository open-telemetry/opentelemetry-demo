"""Unit tests for telemetry.py with mocked backends (no Docker needed).
Run: python -m pytest tests -q
"""
import json

import httpx
import pytest

import telemetry as t


def _use(handler, monkeypatch, tmp_path, inventory=("frontend", "checkout", "payment")):
    monkeypatch.setattr(t, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(t, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr(t, "_inventory", (t.time.time(), list(inventory)))


def test_rejects_bad_and_unknown_services(monkeypatch, tmp_path):
    _use(lambda r: httpx.Response(200, json={}), monkeypatch, tmp_path)
    for bad in ["payment; drop", "flagd", "PAYMENT", "nosuchservice", ""]:
        with pytest.raises(t.TelemetryInputError):
            t.validate_service(bad)
    with pytest.raises(t.TelemetryInputError):
        t.query_metrics("payment", "rm -rf", 5)
    with pytest.raises(t.TelemetryInputError):
        t.query_metrics("payment", "error_rate", 999)
    with pytest.raises(t.TelemetryInputError):
        t.run_tool("delete_everything", {})


def test_unreachable_backend_is_unavailable_not_healthy(monkeypatch, tmp_path):
    def down(request):
        raise httpx.ConnectError("refused", request=request)
    _use(down, monkeypatch, tmp_path)
    res = t.query_metrics("payment", "error_rate", 5)
    assert res.status == t.ToolStatus.UNAVAILABLE
    assert (tmp_path / f"{res.evidence_id}.json").exists()


def test_nan_error_rate_is_empty(monkeypatch, tmp_path):
    body = {"status": "success", "data": {"result": [{"metric": {}, "value": [0, "NaN"]}]}}
    _use(lambda r: httpx.Response(200, json=body), monkeypatch, tmp_path)
    res = t.query_metrics("payment", "error_rate", 5)
    assert res.status == t.ToolStatus.EMPTY
    assert "cannot judge" in res.message


def test_metric_ok_and_query_uses_template(monkeypatch, tmp_path):
    seen = {}

    def handler(request):
        seen["q"] = request.url.params["query"]
        return httpx.Response(200, json={"status": "success",
                                         "data": {"result": [{"metric": {}, "value": [0, "0.42"]}]}})
    _use(handler, monkeypatch, tmp_path)
    res = t.run_tool("query_metrics", {"service": "payment", "metric": "error_rate", "window_minutes": 5})
    assert res.status == t.ToolStatus.OK and res.value["value"] == 0.42
    assert 'service_name="payment"' in seen["q"] and "STATUS_CODE_ERROR" in seen["q"] and "[5m]" in seen["q"]
    assert "or vector(0)" in seen["q"]  # zero errors with traffic = 0, not empty


def _span(sid, parent, name, error=False, msg="", events=None):
    return {"traceId": "0af7651916cd43dd8448eb211c80319c", "spanId": sid, "parentSpanId": parent,
            "name": name, "startTimeUnixNano": "1000000", "endTimeUnixNano": "51000000",
            "status": {"code": "STATUS_CODE_ERROR", "message": msg} if error else {},
            "events": events or [], "attributes": [
                {"key": "rpc.grpc.status_code", "value": {"intValue": "13"}},
                {"key": "feature_flag.key", "value": {"stringValue": "secret"}}]}


def _rs(service, spans):
    return {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
            "scopeSpans": [{"spans": spans}]}


def test_traces_find_origin_and_hide_flags(monkeypatch, tmp_path):
    flag_event = {"name": "feature_flag.evaluation", "attributes": []}
    body = {"result": {"resourceSpans": [
        _rs("frontend", [_span("00000000000000a1", "", "POST /api/checkout", True, "500")]),
        _rs("checkout", [_span("00000000000000b2", "00000000000000a1", "PlaceOrder", True, "charge failed",
                               [flag_event])]),
        _rs("payment", [_span("00000000000000c3", "00000000000000b2", "charge", True, "Invalid token")]),
        _rs("flagd", [_span("00000000000000d4", "00000000000000c3", "ResolveBoolean")]),
    ]}}
    _use(lambda r: httpx.Response(200, json=body), monkeypatch, tmp_path)
    res = t.search_traces("checkout", 15)
    assert res.status == t.ToolStatus.OK
    tr = res.value["traces"][0]
    assert tr["suspected_origin"]["service"] == "payment"
    assert res.value["error_origin_counts"] == {"payment": 1}
    assert "checkout -> payment" in res.value["edges"]
    assert res.trace_ids == ["0af7651916cd43dd8448eb211c80319c"]
    assert "feature_flag" not in json.dumps(res.value)
    assert "flagd" not in json.dumps(res.value)


def test_traces_404_is_empty(monkeypatch, tmp_path):
    _use(lambda r: httpx.Response(404, json={"error": "not found"}), monkeypatch, tmp_path)
    assert t.search_traces("payment", 15).status == t.ToolStatus.EMPTY


def test_logs_unconfigured_is_unavailable(monkeypatch, tmp_path):
    _use(lambda r: httpx.Response(200, json={}), monkeypatch, tmp_path)
    monkeypatch.setattr(t, "OPENSEARCH_URL", "")
    assert t.query_logs("payment").status == t.ToolStatus.UNAVAILABLE


def test_logs_parse_and_withhold_flag_lines(monkeypatch, tmp_path):
    body = {"schema": [{"name": "@timestamp"}, {"name": "severity.text"}, {"name": "body"}, {"name": "traceId"}],
            "datarows": [["2026-10-23 09:00:00", "ERROR", "Payment request failed. Invalid token.",
                          "0af7651916cd43dd8448eb211c80319c"],
                         ["2026-10-23 09:00:01", "WARN", "flagd evaluation paymentFailure=1", ""]]}
    _use(lambda r: httpx.Response(200, json=body), monkeypatch, tmp_path)
    monkeypatch.setattr(t, "OPENSEARCH_URL", "http://os:9200")
    res = t.query_logs("payment", 10, "WARN")
    assert res.status == t.ToolStatus.OK and res.value["count"] == 1
    assert "withheld" in res.message
    assert "paymentFailure" not in json.dumps(res.model_dump(mode="json")["value"])


def test_logs_read_nested_severity(monkeypatch, tmp_path):
    body = {"schema": [{"name": "severity"}, {"name": "@timestamp"}, {"name": "body"}, {"name": "traceId"},
                       {"name": "_id"}],
            "datarows": [[{"number": 17, "text": "error"}, "2026-10-23 09:00:00", "Payment request failed.", "",
                          "oDRmaKEBC5GIrfqg5U64"]]}
    _use(lambda r: httpx.Response(200, json=body), monkeypatch, tmp_path)
    monkeypatch.setattr(t, "OPENSEARCH_URL", "http://os:9200")
    res = t.query_logs("payment", 10, "WARN")
    assert res.value["lines"][0]["severity"] == "error"
    assert res.log_ids == ["oDRmaKEBC5GIrfqg5U64"]


def test_health_does_not_expose_uncitable_sub_ids(monkeypatch, tmp_path):
    body = {"status": "success", "data": {"result": [{"metric": {}, "value": [0, "1.5"]}]}}
    _use(lambda r: httpx.Response(200, json=body), monkeypatch, tmp_path)
    res = t.service_health("payment", 5)
    assert res.status == t.ToolStatus.OK and res.source == "derived"
    assert "ev-query_metrics" not in res.for_llm()  # only res.evidence_id is citable
    assert "sub_evidence" in (tmp_path / f"{res.evidence_id}.json").read_text()  # still auditable on disk


def test_tool_specs_are_valid_for_llm():
    names = {s["function"]["name"] for s in t.tool_specs()}
    assert names == {"overview", "query_metrics", "search_traces", "query_logs", "service_health"}
