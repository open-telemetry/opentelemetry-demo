"""Regression tests for feature-flag data sanitization and safety boundaries."""
from __future__ import annotations

import json
from typing import Any, Dict
import pytest

from src.agent.tools import (
    EXCLUDED_SERVICES,
    ToolBox,
    ToolContext,
    container_health,
    dependency_map,
    get_service_metrics,
    search_logs,
    search_traces,
    strip_flag_data,
)


def test_strip_flag_data_drops_flag_attributes_and_events():
    dirty_span = {
        "name": "checkout.placeOrder",
        "traceId": "a" * 32,
        "spanId": "b" * 16,
        "attributes": [
            {"key": "http.status_code", "value": {"intValue": 500}},
            {"key": "feature_flag.key", "value": {"stringValue": "paymentFailure"}},
            {"key": "feature_flag.variant", "value": {"stringValue": "on"}},
            {"key": "openfeature.eval.reason", "value": {"stringValue": "TARGETING_MATCH"}},
            {"key": "service.name", "value": {"stringValue": "checkout"}},
        ],
        "events": [
            {"name": "exception", "attributes": [{"key": "exception.message", "value": "rpc timeout"}]},
            {"name": "feature_flag", "attributes": [{"key": "flag.key", "value": "test"}]},
            {"name": "flagd.eval", "attributes": []},
        ],
        "feature_flag_summary": {"enabled": True},
    }

    clean = strip_flag_data(dirty_span)

    # Flag attributes and events must be completely gone
    clean_json = json.dumps(clean)
    assert "paymentFailure" not in clean_json
    assert "feature_flag" not in clean_json
    assert "openfeature" not in clean_json
    assert "flagd" not in clean_json

    # Legitimate attributes and events must be preserved
    attr_keys = [a["key"] for a in clean["attributes"]]
    assert "http.status_code" in attr_keys
    assert "service.name" in attr_keys
    event_names = [e["name"] for e in clean["events"]]
    assert event_names == ["exception"]
    assert clean["name"] == "checkout.placeOrder"


def test_strip_flag_data_preserves_legitimate_telemetry():
    legitimate_payload = {
        "service": "payment",
        "operation": "Charge",
        "error_rate": 0.42,
        "p95_ms": 128.5,
        "spans": [
            {
                "traceId": "1234567890abcdef1234567890abcdef",
                "spanId": "fedcba0987654321",
                "name": "oteldemo.PaymentService/Charge",
                "attributes": [
                    {"key": "rpc.grpc.status_code", "value": {"intValue": 14}},
                    {"key": "net.peer.name", "value": {"stringValue": "payment"}},
                ],
            }
        ],
    }

    cleaned = strip_flag_data(legitimate_payload)
    assert cleaned == legitimate_payload


def test_search_logs_filters_flag_bodies(monkeypatch: pytest.MonkeyPatch):
    fake_hits = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                {
                    "_source": {
                        "observedTimestamp": "2026-10-23T18:00:00Z",
                        "severity.text": "ERROR",
                        "body": "Payment Gateway Timeout: connection reset by peer",
                        "traceId": "t1",
                        "resource": {"service": {"name": "payment"}},
                    }
                },
                {
                    "_source": {
                        "observedTimestamp": "2026-10-23T18:00:01Z",
                        "severity.text": "WARN",
                        "body": "flagd evaluation returned variant: paymentFailure=on",
                        "traceId": "t2",
                        "resource": {"service": {"name": "checkout"}},
                    }
                },
            ],
        }
    }

    mock_os = type("MockOS", (), {"search": lambda self, index, query_dsl: fake_hits})()
    ctx = ToolContext(prometheus=object(), jaeger=object(), opensearch=mock_os, docker_runner=lambda args: "[]")

    res = search_logs(ctx, level="warn", window_minutes=5)
    assert res["status"] == "ok"
    lines = res["data"]["lines"]
    assert len(lines) == 1
    assert "Payment Gateway Timeout" in lines[0]["body"]
    assert "flagd" not in json.dumps(res)


@pytest.mark.parametrize("flag_svc", ["flagd", "flagd-ui"])
def test_all_tools_reject_excluded_flag_services(flag_svc: str):
    ctx = ToolContext(
        prometheus=object(),
        jaeger=object(),
        opensearch=object(),
        docker_runner=lambda args: "[]",
    )

    res_metrics = get_service_metrics(ctx, service=flag_svc)
    assert res_metrics["status"] == "error"
    assert "off-limits" in res_metrics["summary"]

    res_traces = search_traces(ctx, service=flag_svc)
    assert res_traces["status"] == "error"
    assert "off-limits" in res_traces["summary"]

    res_logs = search_logs(ctx, service=flag_svc)
    assert res_logs["status"] == "error"
    assert "off-limits" in res_logs["summary"]

    res_health = container_health(ctx, service=flag_svc)
    assert res_health["status"] == "error"
    assert "off-limits" in res_health["summary"]

    res_dep = dependency_map(ctx, service=flag_svc)
    assert res_dep["status"] == "error"
    assert "off-limits" in res_dep["summary"]


def test_toolbox_execute_automatically_sanitizes():
    def fake_tool(ctx, **kw):
        return {
            "tool": "fake_tool",
            "status": "ok",
            "summary": "ok",
            "data": {
                "safe_field": 123,
                "feature_flag_active": "paymentFailure",
                "nested": [{"feature_flag.name": "secret_flag", "valid": True}],
            },
            "evidence": [],
        }

    specs = [{"name": "fake_tool", "description": "test tool", "parameters": {"type": "object"}}]
    box = ToolBox(ctx=object(), impls={"fake_tool": fake_tool}, specs=specs)
    res = box.execute("fake_tool", {})
    dump = json.dumps(res)
    assert "paymentFailure" not in dump
    assert "secret_flag" not in dump
    assert res["data"]["safe_field"] == 123
    assert res["data"]["nested"][0]["valid"] is True

def test_strip_flag_data_drops_flag_evidence_references():
    evidence_bundle = [
        {"ref": "span:abc12345", "kind": "trace", "value": "checkout"},
        {"ref": "span:flagd_eval_span", "kind": "trace", "value": "flagd"},
        {"ref": "metric:payment:grpc_timeout", "kind": "metric", "value": 0.5},
        {"ref": "metric:openfeature_evaluations_total", "kind": "metric", "value": 10},
    ]
    cleaned = strip_flag_data(evidence_bundle)
    refs = [e["ref"] for e in cleaned]
    assert "span:abc12345" in refs
    assert "metric:payment:grpc_timeout" in refs
    assert "span:flagd_eval_span" not in refs
    assert "metric:openfeature_evaluations_total" not in refs
