import json
from pathlib import Path
import jsonschema
import pytest

from src.analysis.root_cause_analyzer import RootCauseAnalyzer
from src.models.evidence import EvidenceBundle, MetricDataPoint
from src.models.diagnosis import DiagnosisStatus, FailureMode


@pytest.fixture
def analyzer():
    return RootCauseAnalyzer()


def test_clear_root_cause_multiple_signals(analyzer):
    """Rule 1: Corroborated error traces, logs, and metric deviations confirm an internal root cause."""
    bundle = EvidenceBundle(
        service_name="ad",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=["trace-ad-001", "trace-ad-002"],
        metrics=[
            MetricDataPoint(
                metric_name="http_error_rate_ratio",
                service="ad",
                baseline_value=0.0,
                observed_value=0.45,
                unit="ratio",
                timestamp="2026-10-23T15:00:00Z",
            )
        ],
        log_excerpts=[
            "[2026-10-23T15:00:00Z] [ERROR] ad: AdService.GetAds failed with InternalServerError"
        ],
        dependency_graph={"upstream": ["frontend"], "downstream": []},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"},
            "source_errors": {"jaeger": None, "prometheus": None, "opensearch": None},
            "all_sources_available": True,
            "partial_failure": False,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    assert diagnosis.status == DiagnosisStatus.CONFIRMED
    assert diagnosis.investigated_service == "ad"
    assert diagnosis.primary_root_cause is not None
    assert diagnosis.primary_root_cause.service == "ad"
    assert diagnosis.primary_root_cause.failure_mode == FailureMode.INTERNAL_SERVICE_ERROR
    assert diagnosis.primary_root_cause.is_dependency is False
    assert diagnosis.overall_confidence >= 0.70
    assert len(diagnosis.contradictory_evidence) == 0
    assert len(diagnosis.missing_evidence) == 0


def test_upstream_dependency_failure_affecting_downstream_service(analyzer):
    """Rule 2: A dependency showing errors is identified as the root cause over the downstream caller."""
    bundle = EvidenceBundle(
        service_name="cart",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=["trace-cart-valkey-fail"],
        metrics=[
            MetricDataPoint(
                metric_name="http_error_rate_ratio",
                service="cart",
                baseline_value=0.0,
                observed_value=0.35,
                unit="ratio",
                timestamp="2026-10-23T15:00:00Z",
            )
        ],
        log_excerpts=[
            "[2026-10-23T15:00:00Z] [ERROR] cart: Connection refused to Valkey instance at valkey-cart:6379"
        ],
        dependency_graph={"upstream": ["frontend", "checkout"], "downstream": ["valkey-cart"]},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"},
            "source_errors": {},
            "all_sources_available": True,
            "partial_failure": False,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    assert diagnosis.status == DiagnosisStatus.CONFIRMED
    assert diagnosis.primary_root_cause is not None
    # valkey-cart is identified as the root cause, NOT cart
    assert diagnosis.primary_root_cause.service == "valkey-cart"
    assert diagnosis.primary_root_cause.is_dependency is True
    assert diagnosis.primary_root_cause.failure_mode == FailureMode.DEPENDENCY_OUTAGE
    assert diagnosis.primary_root_cause.rank == 1

    # Cart is identified as a cascading victim
    assert len(diagnosis.candidates) >= 2
    victim = diagnosis.candidates[1]
    assert victim.service == "cart"
    assert victim.failure_mode == FailureMode.CASCADING_SYMPTOMATIC_FAILURE
    assert victim.rank == 2
    assert diagnosis.primary_root_cause.confidence > victim.confidence


def test_latency_only_incident(analyzer):
    """Rule 3: Latency increases without errors indicate performance degradation rather than crashes."""
    bundle = EvidenceBundle(
        service_name="recommendation",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=[],  # No error traces
        metrics=[
            MetricDataPoint(
                metric_name="p95_request_latency",
                service="recommendation",
                baseline_value=60.0,
                observed_value=3200.0,
                unit="ms",
                timestamp="2026-10-23T15:00:00Z",
            ),
            MetricDataPoint(
                metric_name="http_error_rate_ratio",
                service="recommendation",
                baseline_value=0.0,
                observed_value=0.0,
                unit="ratio",
                timestamp="2026-10-23T15:00:00Z",
            ),
        ],
        log_excerpts=[],  # No error logs
        dependency_graph={"upstream": ["frontend"], "downstream": ["product-catalog"]},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"},
            "all_sources_available": True,
            "partial_failure": False,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    assert diagnosis.status == DiagnosisStatus.DEGRADED_PERFORMANCE
    assert diagnosis.primary_root_cause is not None
    assert diagnosis.primary_root_cause.service == "recommendation"
    assert diagnosis.primary_root_cause.failure_mode == FailureMode.LATENCY_DEGRADATION
    assert "performance degradation" in diagnosis.primary_root_cause.reasoning.lower()


def test_missing_telemetry_reduces_confidence(analyzer):
    """Rule 5: Unavailable telemetry backends reduce confidence and cannot yield CONFIRMED status."""
    bundle = EvidenceBundle(
        service_name="payment",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=["trace-pay-001"],
        metrics=[],  # Missing because Prometheus failed
        log_excerpts=["[ERROR] payment: unhandled rejection in charge card"],
        dependency_graph={"upstream": ["checkout"], "downstream": []},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "unavailable", "opensearch": "available"},
            "source_errors": {"prometheus": "Connection refused to http://prometheus:9090"},
            "all_sources_available": False,
            "partial_failure": True,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    # Cannot be CONFIRMED due to missing Prometheus
    assert diagnosis.status == DiagnosisStatus.SUSPECTED
    assert len(diagnosis.missing_evidence) == 1
    assert "prometheus" in diagnosis.missing_evidence[0].lower()
    assert diagnosis.scoring_breakdown["telemetry_availability_penalty"] < 0.0


def test_total_telemetry_outage(analyzer):
    """Rule 4 & 5: When all telemetry stores are down, analyzer reports INSUFFICIENT_EVIDENCE with 0 confidence."""
    bundle = EvidenceBundle(
        service_name="shipping",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=[],
        metrics=[],
        log_excerpts=[],
        dependency_graph={"upstream": ["checkout"], "downstream": ["quote"]},
        metadata={
            "source_status": {"jaeger": "unavailable", "prometheus": "unavailable", "opensearch": "unavailable"},
            "source_errors": {
                "jaeger": "Timeout",
                "prometheus": "Connection refused",
                "opensearch": "503 Service Unavailable",
            },
            "all_sources_available": False,
            "partial_failure": True,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    assert diagnosis.status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert diagnosis.overall_confidence == 0.0
    assert len(diagnosis.missing_evidence) == 3


def test_conflicting_evidence_detection(analyzer):
    """Rule 6: Conflicting signals between metrics and trace/log stores are explicitly surfaced."""
    bundle = EvidenceBundle(
        service_name="email",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=[],  # No error traces
        metrics=[
            MetricDataPoint(
                metric_name="http_error_rate_ratio",
                service="email",
                baseline_value=0.0,
                observed_value=0.55,  # High error rate!
                unit="ratio",
                timestamp="2026-10-23T15:00:00Z",
            )
        ],
        log_excerpts=[],  # No error logs
        dependency_graph={"upstream": ["checkout"], "downstream": []},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"},
            "all_sources_available": True,
            "partial_failure": False,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    assert len(diagnosis.contradictory_evidence) > 0
    assert "promethe" in diagnosis.contradictory_evidence[0].lower()
    # Conflicting evidence must prevent full CONFIRMED status
    assert diagnosis.status != DiagnosisStatus.CONFIRMED
    assert diagnosis.scoring_breakdown["conflicting_evidence_penalty"] < 0.0


def test_empty_evidence_clean_system(analyzer):
    """All backends available and 0 anomalies found correctly yields NO_ANOMALY_DETECTED."""
    bundle = EvidenceBundle(
        service_name="currency",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=[],
        metrics=[],
        log_excerpts=[],
        dependency_graph={"upstream": ["frontend", "checkout"], "downstream": []},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"},
            "all_sources_available": True,
            "partial_failure": False,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    assert diagnosis.status == DiagnosisStatus.NO_ANOMALY_DETECTED
    assert diagnosis.overall_confidence == 0.0
    assert diagnosis.primary_root_cause is None
    assert len(diagnosis.candidates) == 0


def test_empty_evidence_with_missing_backend_is_not_healthy(analyzer):
    """Rule 4: A service with no errors but missing telemetry cannot be confirmed healthy."""
    bundle = EvidenceBundle(
        service_name="currency",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=[],
        metrics=[],
        log_excerpts=[],
        dependency_graph={"upstream": ["frontend", "checkout"], "downstream": []},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "unavailable", "opensearch": "available"},
            "source_errors": {"prometheus": "Connection refused"},
            "all_sources_available": False,
            "partial_failure": True,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    assert diagnosis.status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert diagnosis.overall_confidence == 0.0
    assert len(diagnosis.missing_evidence) == 1


def test_multiple_plausible_root_causes(analyzer):
    """Multiple failing dependencies are correctly identified and ranked."""
    bundle = EvidenceBundle(
        service_name="checkout",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=["trace-chk-01", "trace-chk-02"],
        metrics=[
            MetricDataPoint(
                metric_name="http_error_rate_ratio",
                service="checkout",
                baseline_value=0.0,
                observed_value=0.60,
                unit="ratio",
                timestamp="2026-10-23T15:00:00Z",
            )
        ],
        log_excerpts=[
            "[ERROR] checkout: Payment service payment:50051 unavailable deadline exceeded",
            "[ERROR] checkout: Shipping service shipping:50050 failed with connection refused",
        ],
        dependency_graph={"upstream": ["frontend"], "downstream": ["payment", "shipping"]},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"},
            "all_sources_available": True,
            "partial_failure": False,
        },
    )

    diagnosis = analyzer.diagnose(bundle)

    assert len(diagnosis.candidates) >= 2
    candidate_services = [c.service for c in diagnosis.candidates]
    assert "payment" in candidate_services
    assert "shipping" in candidate_services
    assert "checkout" in candidate_services
    # Ranks are distinct and sequential
    ranks = [c.rank for c in diagnosis.candidates]
    assert ranks == list(range(1, len(diagnosis.candidates) + 1))


def test_confidence_calibration_and_ranking_consistency(analyzer):
    """Verify that confidence monotonically reflects signal strength and availability."""
    # Bundle 1: 3 signals available (Traces + Logs + Metrics)
    bundle_3_signals = EvidenceBundle(
        service_name="ad",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=["t1"],
        metrics=[MetricDataPoint(metric_name="error_rate", service="ad", baseline_value=0.0, observed_value=0.5, timestamp="t")],
        log_excerpts=["[ERROR] ad internal error"],
        dependency_graph={"upstream": [], "downstream": []},
        metadata={"source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"}},
    )

    # Bundle 2: 2 signals (Traces + Logs, no metric anomaly)
    bundle_2_signals = EvidenceBundle(
        service_name="ad",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=["t1"],
        metrics=[],
        log_excerpts=["[ERROR] ad internal error"],
        dependency_graph={"upstream": [], "downstream": []},
        metadata={"source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"}},
    )

    # Bundle 3: 1 signal (Traces only)
    bundle_1_signal = EvidenceBundle(
        service_name="ad",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=["t1"],
        metrics=[],
        log_excerpts=[],
        dependency_graph={"upstream": [], "downstream": []},
        metadata={"source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"}},
    )

    diag_3 = analyzer.diagnose(bundle_3_signals)
    diag_2 = analyzer.diagnose(bundle_2_signals)
    diag_1 = analyzer.diagnose(bundle_1_signal)

    assert diag_3.overall_confidence > diag_2.overall_confidence
    assert diag_2.overall_confidence > diag_1.overall_confidence


def test_diagnosis_to_incident_report_validates_json_schema(analyzer):
    """The converted IncidentReport must strictly validate against config/incident_schema.json."""
    schema_path = Path(__file__).resolve().parent.parent / "config" / "incident_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    bundle = EvidenceBundle(
        service_name="cart",
        detection_timestamp="2026-10-23T15:00:00Z",
        trace_ids=["4bf92f3577b34da6a3ce929d0e0e4736"],
        metrics=[
            MetricDataPoint(
                metric_name="http_error_rate_ratio",
                service="cart",
                baseline_value=0.0,
                observed_value=0.75,
                unit="ratio",
                timestamp="2026-10-23T15:00:00Z",
            )
        ],
        log_excerpts=["[ERROR] cart: Connection refused to Valkey instance at valkey-cart:6379"],
        dependency_graph={"upstream": ["frontend"], "downstream": ["valkey-cart"]},
        metadata={
            "source_status": {"jaeger": "available", "prometheus": "available", "opensearch": "available"},
            "all_sources_available": True,
            "partial_failure": False,
        },
    )

    diagnosis = analyzer.diagnose(bundle)
    incident_report = diagnosis.to_incident_report(
        incident_id="INC-20261023-VALKEY-01",
        recommended_action="Restart valkey-cart container or verify network bridge connectivity",
    )

    data = incident_report.to_schema_dict()
    # JSON schema validation draft 2020-12
    jsonschema.validate(instance=data, schema=schema)
    assert data["target_service"] == "valkey-cart"
    assert "cart" in data["impacted_services"]
