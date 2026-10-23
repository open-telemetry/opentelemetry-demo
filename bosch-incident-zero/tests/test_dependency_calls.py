"""Rule 2a: a failing call to an unreachable dependency blames the dependency, not the caller.

Fixtures are sanitized Jaeger v3 (OTLP JSON) traces modelled on live demo runs.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock

import jsonschema

from src.analysis.dependency_calls import callee_of, find_failed_dependency_calls
from src.analysis.root_cause_analyzer import RootCauseAnalyzer
from src.evidence.collector import EvidenceCollector
from src.models.diagnosis import DiagnosisStatus, FailureMode
from src.models.evidence import EvidenceBundle, MetricDataPoint
from src.telemetry.jaeger_client import JaegerClient
from src.telemetry.opensearch_client import OpenSearchClient
from src.telemetry.prometheus_client import PrometheusClient

TRACE = "25a4efaf34648e3e87e940d59b6ae03d"
ALL_UP = {"source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"}}


def span(span_id, parent, name, kind, error=None, **attrs):
    s = {
        "traceId": TRACE,
        "spanId": span_id,
        "name": name,
        "kind": kind,
        "status": {"code": 2, "message": error} if error else {},
        "attributes": [{"key": k.replace("_", "."), "value": {"stringValue": v}} for k, v in attrs.items()],
    }
    if parent:
        s["parentSpanId"] = parent
    return s


def trace(*services):
    """services: (service_name, [spans]) pairs -> a Jaeger v3 /traces response."""
    return {"result": {"resourceSpans": [
        {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": svc}}]},
         "scopeSpans": [{"spans": spans}]}
        for svc, spans in services
    ]}}


PAYMENT_UNREACHABLE = trace(
    ("frontend", [span("f1", None, "oteldemo.CheckoutService/PlaceOrder", 3,
                       "rpc error: code = Unavailable desc = failed to charge card")]),
    ("checkout", [
        span("c1", "f1", "oteldemo.CheckoutService/PlaceOrder", 2,
             "failed to charge card: could not charge the card: rpc error: code = Unavailable "
             "desc = name resolver error: produced zero addresses"),
        span("c2", "c1", "oteldemo.PaymentService/Charge", 3,
             "name resolver error: produced zero addresses", rpc_method="Charge"),
    ]),
)


def test_unreachable_callee_is_detected():
    calls = find_failed_dependency_calls(PAYMENT_UNREACHABLE)
    assert calls == [{
        "trace_id": TRACE,
        "caller": "checkout",
        "callee": "payment",
        "operation": "oteldemo.PaymentService/Charge",
        "error": "name resolver error: produced zero addresses",
        "callee_reached": False,
    }]


def test_pass_through_caller_is_not_blamed():
    # frontend -> checkout was reached and failed, but only because checkout -> payment failed.
    callees = [c["callee"] for c in find_failed_dependency_calls(PAYMENT_UNREACHABLE)]
    assert "checkout" not in callees


def test_reached_callee_failing_internally_is_the_cause():
    raw = trace(
        ("frontend", [span("f1", None, "oteldemo.ProductCatalogService/GetProduct", 3, "rpc error: code = Internal")]),
        ("product-catalog", [span("p1", "f1", "oteldemo.ProductCatalogService/GetProduct", 2, "product not found")]),
    )
    assert find_failed_dependency_calls(raw) == [{
        "trace_id": TRACE, "caller": "frontend", "callee": "product-catalog",
        "operation": "oteldemo.ProductCatalogService/GetProduct",
        "error": "rpc error: code = Internal", "callee_reached": True,
    }]


def test_callee_that_succeeded_is_not_blamed():
    raw = trace(
        ("checkout", [span("c1", None, "oteldemo.EmailService/SendOrderConfirmation", 3, "context deadline exceeded")]),
        ("email", [span("e1", "c1", "POST /send_order_confirmation", 2)]),
    )
    assert find_failed_dependency_calls(raw) == []


def test_callee_mapping_from_attributes():
    assert callee_of(span("x", None, "HGET", 3, db_system="redis")) == "valkey-cart"
    assert callee_of(span("x", None, "orders publish", 4, messaging_system="kafka")) == "kafka"
    assert callee_of(span("x", None, "POST", 3, url_full="http://email:6060/send_order_confirmation")) == "email"
    assert callee_of(span("x", None, "GET", 3, server_address="example.com")) is None


def test_bad_input_returns_no_calls():
    assert find_failed_dependency_calls(None) == []
    assert find_failed_dependency_calls({"result": {}}) == []


def checkout_bundle():
    return EvidenceBundle(
        service_name="checkout",
        detection_timestamp="2026-10-23T11:50:00Z",
        trace_ids=[TRACE],
        failed_dependency_calls=find_failed_dependency_calls(PAYMENT_UNREACHABLE),
        metrics=[MetricDataPoint(metric_name="error_rate_ratio", service="checkout",
                                 baseline_value=0.0, observed_value=0.42, timestamp="t")],
        dependency_graph={"upstream": ["frontend"], "downstream": ["payment", "cart"]},
        metadata=ALL_UP,
    )


def test_analyzer_names_unreachable_dependency_as_root_cause():
    diagnosis = RootCauseAnalyzer().diagnose(checkout_bundle())
    root = diagnosis.primary_root_cause
    assert root.service == "payment"
    assert root.failure_mode == FailureMode.DEPENDENCY_OUTAGE
    assert root.is_dependency
    assert "never reached" in " ".join(root.supporting_signals)
    victim = next(c for c in diagnosis.candidates if c.service == "checkout")
    assert victim.failure_mode == FailureMode.CASCADING_SYMPTOMATIC_FAILURE
    assert victim.confidence < root.confidence
    assert diagnosis.status == DiagnosisStatus.CONFIRMED


def test_report_targets_dependency_and_lists_caller_as_impacted():
    report = RootCauseAnalyzer().diagnose(checkout_bundle()).to_incident_report("INC-TEST-2A").to_schema_dict()
    assert report["target_service"] == "payment"
    assert report["impacted_services"] == ["checkout"]
    schema = json.loads((Path(__file__).parent.parent / "config" / "incident_schema.json").read_text())
    jsonschema.validate(report, schema)


def test_without_span_evidence_the_old_behaviour_holds():
    bundle = checkout_bundle()
    bundle.failed_dependency_calls = []
    assert RootCauseAnalyzer().diagnose(bundle).primary_root_cause.service == "checkout"


def test_collector_records_failed_dependency_calls():
    jaeger = MagicMock(spec=JaegerClient)
    jaeger.get_error_trace_ids.return_value = [TRACE]
    jaeger.get_traces.return_value = PAYMENT_UNREACHABLE
    prometheus = MagicMock(spec=PrometheusClient)
    prometheus.get_service_metrics.return_value = []
    opensearch = MagicMock(spec=OpenSearchClient)
    opensearch.get_error_logs.return_value = []

    bundle = EvidenceCollector(jaeger, prometheus, opensearch).collect_evidence("checkout")
    assert [c["callee"] for c in bundle.failed_dependency_calls] == ["payment"]
    assert jaeger.get_traces.call_args.kwargs["errors_only"] is True


def test_report_lists_every_caller_on_the_failing_path():
    bundle = checkout_bundle()
    bundle.service_name = "frontend"
    report = RootCauseAnalyzer().diagnose(bundle).to_incident_report("INC-TEST-2B").to_schema_dict()
    assert report["target_service"] == "payment"
    assert report["impacted_services"] == ["frontend", "checkout"]
