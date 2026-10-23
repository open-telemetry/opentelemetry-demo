import json
import re

import pytest

from app.tools.containers import get_container_health
from app.tools.deployments import get_recent_changes
from app.tools.diagnosis import submit_diagnosis
from app.tools.jaeger import get_trace, search_traces
from app.tools.logs import search_logs
from app.tools.memory import search_incident_memory
from app.tools.prometheus import get_health_overview, query_prometheus
from app.tools.registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS, execute_tool


def test_registry_schema_definitions() -> None:
    assert len(TOOL_DEFINITIONS) == 9
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    expected = {
        "get_health_overview",
        "query_prometheus",
        "search_traces",
        "get_trace",
        "search_logs",
        "get_container_health",
        "get_recent_changes",
        "search_incident_memory",
        "submit_diagnosis",
    }
    assert names == expected
    for t in TOOL_DEFINITIONS:
        assert t["type"] == "function"
        fn = t["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_get_health_overview_live() -> None:
    res = get_health_overview(lookback_min=15)
    assert isinstance(res, str)
    assert len(res) <= 2000
    assert "Service" in res
    assert "Error %" in res
    assert "|" in res


def test_query_prometheus_live() -> None:
    query = "sum by (service_name) (rate(traces_span_metrics_calls_total[2m]))"
    res = query_prometheus(promql=query, lookback_min=15)
    assert isinstance(res, str)
    assert len(res) <= 2000
    assert "last=" in res or "points=" in res or "PromQL:" in res


def test_search_traces_live() -> None:
    res = search_traces(service="payment", lookback_min=30, limit=3)
    assert isinstance(res, str)
    assert len(res) <= 2000
    assert "payment" in res.lower() or "traces" in res.lower()


def test_get_trace_and_strip_feature_flags() -> None:
    # First find a trace ID from search_traces
    search_res = search_traces(service="payment", lookback_min=60, limit=5)
    # Match 32-character hexadecimal trace IDs
    match = re.search(r"\b([0-9a-fA-F]{32})\b", search_res)
    if match:
        trace_id = match.group(1)
        res = get_trace(trace_id=trace_id)
        assert isinstance(res, str)
        assert len(res) <= 2000
        assert trace_id in res
        # HARD RULE 1: Never leak feature_flag.* attributes!
        assert "feature_flag" not in res.lower(), "feature_flag attribute was leaked in get_trace output!"
    else:
        # If no trace found, test with mock/unknown trace ID
        res = get_trace(trace_id="00000000000000000000000000000000")
        assert "not found" in res.lower()


def test_search_logs_live() -> None:
    res = search_logs(service="payment", lookback_min=30, limit=5)
    assert isinstance(res, str)
    assert len(res) <= 2000


def test_search_logs_blocks_flagd_hard_rule_1() -> None:
    for blocked_svc in ("flagd", "flagd-ui"):
        res = search_logs(service=blocked_svc)
        assert "prohibited by Hard Rule 1" in res


def test_get_container_health_single_and_all() -> None:
    res_single = get_container_health(service="payment")
    assert isinstance(res_single, str)
    assert len(res_single) <= 2000
    assert "payment" in res_single
    assert "State:" in res_single

    res_all = get_container_health()
    assert isinstance(res_all, str)
    assert len(res_all) <= 2000
    assert "| Service | State | Health |" in res_all


def test_get_recent_changes_live() -> None:
    res = get_recent_changes(lookback_min=60)
    assert isinstance(res, str)
    assert len(res) <= 2000


def test_search_incident_memory() -> None:
    res = search_incident_memory(symptom_summary="payment charge failures and timeouts")
    assert isinstance(res, str)
    assert len(res) <= 2000
    assert "memory" in res.lower()


def test_submit_diagnosis_validation() -> None:
    valid_evidence = [
        {
            "evidence_id": "E1",
            "type": "metric",
            "ref": "payment error_pct=100.0%",
            "why_it_matters": "All payment calls failing",
        }
    ]
    res_valid = submit_diagnosis(
        component="payment",
        cause_category="service_fault_injected_errors",
        cause_description="Payment service mock error injected",
        confidence=0.95,
        evidence=valid_evidence,
        alternatives_considered=["dependency_unavailable"],
        recommended_runbook_ids=["RB-PAYMENT-FLAG"],
    )
    assert "Diagnosis submitted successfully" in res_valid

    # Test invalid category
    res_bad_cat = submit_diagnosis(
        component="payment",
        cause_category="alien_invasion",
        cause_description="Payment failing",
        confidence=0.95,
        evidence=valid_evidence,
    )
    assert "Validation Error" in res_bad_cat
    assert "cause_category" in res_bad_cat

    # Test invalid confidence
    res_bad_conf = submit_diagnosis(
        component="payment",
        cause_category="service_fault_injected_errors",
        cause_description="Payment failing",
        confidence=1.5,
        evidence=valid_evidence,
    )
    assert "Validation Error" in res_bad_conf
    assert "confidence" in res_bad_conf


def test_execute_tool_compact_output_limit() -> None:
    for name in TOOL_FUNCTIONS.keys():
        if name == "submit_diagnosis":
            args = {
                "component": "payment",
                "cause_category": "unknown",
                "cause_description": "investigating",
                "confidence": 0.5,
                "evidence": [{"evidence_id": "E1", "type": "metric", "ref": "err", "why_it_matters": "test"}],
            }
        elif name in ("search_traces", "search_logs"):
            args = {"service": "payment"}
        elif name == "query_prometheus":
            args = {"promql": "up"}
        elif name == "get_trace":
            args = {"trace_id": "mock"}
        elif name == "search_incident_memory":
            args = {"symptom_summary": "payment error"}
        else:
            args = {}

        output = execute_tool(name, args)
        assert isinstance(output, str)
        assert len(output) <= 2000, f"Tool '{name}' output exceeded 2000 characters: length={len(output)}"
