"""Offline tests for Person 4's read-only tools. Backends are replaced with recorded-shape fake data."""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from oncall.clients import backends
from oncall.tools import deploys, logs, traces

TRACE = "f695f778aa11bb22cc33dd44ee55ff66"


def _span(span_id, parent, service, name, error=False, message=""):
    return {"traceId": TRACE, "spanId": span_id, "parentSpanId": parent, "service": service, "name": name,
            "status": {"code": 2, "message": message} if error else {}, "attributes": [], "events": []}


def test_failed_traces_names_the_deepest_failing_service(monkeypatch):
    spans = [_span("a", None, "frontend", "POST /api/checkout", True, "500"),
             _span("b", "a", "checkout", "PlaceOrder", True, "failed to charge card"),
             _span("c", "b", "payment", "charge", True, "Payment request failed. Invalid token."),
             _span("d", "b", "flagd", "flagd.evaluation.v2.Service/ResolveBoolean", True, "boom")]
    monkeypatch.setattr(traces, "jaeger_spans", lambda service, window, num_traces: spans)
    out = traces.get_failed_traces("checkout", 5)
    assert "origin payment span 'charge'" in out.text and "Invalid token" in out.text
    assert "frontend -> checkout -> payment" in out.text
    assert "flagd" not in out.text  # flag-evaluation spans would leak flag state


def test_failed_traces_scans_enough_traces(monkeypatch):
    seen = {}
    monkeypatch.setattr(traces, "jaeger_spans", lambda service, window, num_traces: seen.update(n=num_traces) or [])
    traces.get_failed_traces("checkout", 5)
    assert seen["n"] >= 200  # rare errors are missed in the newest 20 traces


def _log_hit(body, severity, **attributes):
    return {"_source": {"@timestamp": "2026-10-24T04:30:00Z", "body": body, "severity": {"text": severity},
                        "traceId": TRACE, "attributes": attributes}}


def test_logs_find_failures_logged_below_error(monkeypatch):
    captured = {}

    def fake_search(body):
        captured["body"] = body
        return {"hits": {"total": {"value": 2}, "hits": [
            _log_hit("Payment request failed. Invalid token.", "warn"),
            _log_hit("Checkout payment declined", "info", details="could not charge the card: Invalid token")]}}

    monkeypatch.setattr(logs, "opensearch_search", fake_search)
    out = logs.get_logs("payment", 10)
    assert "[warn] Payment request failed. Invalid token." in out.text
    assert "Checkout payment declined | could not charge the card" in out.text  # detail attribute shown
    assert out.facts[0].data["messages"][0]["trace_id"] == TRACE
    query = json.dumps(captured["body"])
    assert '"gte": 13' in query  # WARN or worse, not an exact "ERROR" match
    assert "attributes.*" not in query  # wildcard over attributes exceeds OpenSearch's clause limit


def test_logs_never_show_flag_text(monkeypatch):
    monkeypatch.setattr(logs, "opensearch_search", lambda body: {"hits": {"total": {"value": 1}, "hits": [
        _log_hit("evaluated feature_flag paymentFailure", "warn")]}})
    assert "feature_flag" not in logs.get_logs("payment", 10).text


def test_deploy_history_survives_a_vanished_container(monkeypatch):
    def fake_docker(*args):
        if args[0] == "events":
            return ""
        if args[0] == "ps":
            return "gone1\nalive2\n"
        if args[1] == "gone1":
            raise RuntimeError("docker inspect gone1 failed: No such object")
        return json.dumps([{"Name": "/checkout", "Config": {"Image": "demo:checkout"}, "RestartCount": 2}])

    monkeypatch.setattr(deploys, "docker", fake_docker)
    out = deploys.get_deploy_history(30)
    assert out.facts[0].data["restarted"] == [{"container": "checkout", "image": "demo:checkout", "restarts": 2}]


def _host_settings():
    return SimpleNamespace(ONCALL_MODE="host", JAEGER_URL="http://127.0.0.1:16686/jaeger/ui",
                           OPENSEARCH_URL="http://127.0.0.1:9200")


def test_jaeger_url_falls_back_to_the_published_port(monkeypatch):
    backends.jaeger_url.cache_clear()
    monkeypatch.delenv("JAEGER_URL", raising=False)
    monkeypatch.setattr(backends, "settings", _host_settings())
    monkeypatch.setattr(backends, "docker", lambda *a: "0.0.0.0:57989\n")

    def fake_get(url, timeout):
        if "127.0.0.1:16686" in url:
            raise httpx.ConnectError("refused")
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(backends.httpx, "get", fake_get)
    assert backends.jaeger_url() == "http://localhost:57989/jaeger/ui"
    backends.jaeger_url.cache_clear()


def test_opensearch_url_uses_dockers_random_port(monkeypatch):
    backends.opensearch_url.cache_clear()
    monkeypatch.delenv("OPENSEARCH_URL", raising=False)
    monkeypatch.setattr(backends, "settings", _host_settings())
    monkeypatch.setattr(backends, "docker", lambda *a: "0.0.0.0:59104\n[::]:59104\n")
    assert backends.opensearch_url() == "http://localhost:59104"
    backends.opensearch_url.cache_clear()
