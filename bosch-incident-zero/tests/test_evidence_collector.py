from unittest.mock import MagicMock
import pytest

from src.evidence.collector import EvidenceCollector
from src.models.evidence import MetricDataPoint
from src.telemetry.exceptions import TelemetryConnectionError, TelemetryTimeoutError
from src.telemetry.jaeger_client import JaegerClient
from src.telemetry.opensearch_client import OpenSearchClient
from src.telemetry.prometheus_client import PrometheusClient


@pytest.fixture
def mock_jaeger():
    return MagicMock(spec=JaegerClient)


@pytest.fixture
def mock_prometheus():
    return MagicMock(spec=PrometheusClient)


@pytest.fixture
def mock_opensearch():
    return MagicMock(spec=OpenSearchClient)


def test_collect_evidence_all_success(mock_jaeger, mock_prometheus, mock_opensearch):
    # Setup mocks
    mock_jaeger.get_error_trace_ids.return_value = ["trace-err-101", "trace-err-102"]
    mock_prometheus.get_service_metrics.return_value = [
        MetricDataPoint(
            metric_name="http_error_rate_ratio",
            service="cart",
            baseline_value=0.0,
            observed_value=0.42,
            unit="ratio",
            timestamp="2026-10-23T14:30:00Z",
        )
    ]
    mock_opensearch.get_error_logs.return_value = [
        "[2026-10-23T14:30:00Z] [ERROR] cart: connection refused [traceId=trace-err-101]"
    ]

    collector = EvidenceCollector(
        jaeger_client=mock_jaeger,
        prometheus_client=mock_prometheus,
        opensearch_client=mock_opensearch,
    )

    bundle = collector.collect_evidence(service_name="cart", lookback_seconds=300)

    assert bundle.service_name == "cart"
    assert bundle.trace_ids == ["trace-err-101", "trace-err-102"]
    assert len(bundle.metrics) == 1
    assert bundle.metrics[0].observed_value == 0.42
    assert len(bundle.log_excerpts) == 1
    assert "connection refused" in bundle.log_excerpts[0]

    # Verify dependency topology
    assert "valkey-cart" in bundle.dependency_graph["downstream"]
    assert "frontend" in bundle.dependency_graph["upstream"]
    assert "checkout" in bundle.dependency_graph["upstream"]

    # Verify metadata
    metadata = bundle.metadata
    assert metadata["source_status"]["jaeger"] == "available"
    assert metadata["source_status"]["prometheus"] == "available"
    assert metadata["source_status"]["opensearch"] == "available"
    assert metadata["all_sources_available"] is True
    assert metadata["partial_failure"] is False


def test_collect_evidence_partial_failure(mock_jaeger, mock_prometheus, mock_opensearch):
    # Jaeger succeeds
    mock_jaeger.get_error_trace_ids.return_value = ["trace-jaeger-only-001"]
    # Prometheus fails with connection error
    mock_prometheus.get_service_metrics.side_effect = TelemetryConnectionError(
        "Prometheus host unreachable at http://prometheus:9090"
    )
    # OpenSearch succeeds
    mock_opensearch.get_error_logs.return_value = ["[ERROR] log entry"]

    collector = EvidenceCollector(
        jaeger_client=mock_jaeger,
        prometheus_client=mock_prometheus,
        opensearch_client=mock_opensearch,
    )

    bundle = collector.collect_evidence(service_name="checkout", lookback_seconds=300)

    # Successfully gathered signals are preserved
    assert bundle.trace_ids == ["trace-jaeger-only-001"]
    assert len(bundle.log_excerpts) == 1
    # Metrics is empty due to Prometheus failure
    assert len(bundle.metrics) == 0

    # Source failure is explicitly recorded
    metadata = bundle.metadata
    assert metadata["source_status"]["jaeger"] == "available"
    assert metadata["source_status"]["prometheus"] == "unavailable"
    assert metadata["source_status"]["opensearch"] == "available"
    assert "Prometheus host unreachable" in metadata["source_errors"]["prometheus"]
    assert metadata["all_sources_available"] is False
    assert metadata["partial_failure"] is True


def test_collect_evidence_clean_zero_error_state(mock_jaeger, mock_prometheus, mock_opensearch):
    # All backends respond successfully but return 0 anomalies
    mock_jaeger.get_error_trace_ids.return_value = []
    mock_prometheus.get_service_metrics.return_value = []
    mock_opensearch.get_error_logs.return_value = []

    collector = EvidenceCollector(
        jaeger_client=mock_jaeger,
        prometheus_client=mock_prometheus,
        opensearch_client=mock_opensearch,
    )

    bundle = collector.collect_evidence(service_name="currency", lookback_seconds=300)

    assert bundle.trace_ids == []
    assert bundle.metrics == []
    assert bundle.log_excerpts == []

    # Distinguished from outage: all sources available
    assert bundle.metadata["source_status"]["jaeger"] == "available"
    assert bundle.metadata["source_status"]["prometheus"] == "available"
    assert bundle.metadata["source_status"]["opensearch"] == "available"
    assert bundle.metadata["all_sources_available"] is True
    assert bundle.metadata["partial_failure"] is False


def test_collect_evidence_total_backend_outage(mock_jaeger, mock_prometheus, mock_opensearch):
    # All backends throw errors
    mock_jaeger.get_error_trace_ids.side_effect = TelemetryTimeoutError("Jaeger timed out")
    mock_prometheus.get_service_metrics.side_effect = TelemetryConnectionError("Prometheus down")
    mock_opensearch.get_error_logs.side_effect = TelemetryConnectionError("OpenSearch down")

    collector = EvidenceCollector(
        jaeger_client=mock_jaeger,
        prometheus_client=mock_prometheus,
        opensearch_client=mock_opensearch,
    )

    # Collector does not crash; returns safe bundle with errors documented
    bundle = collector.collect_evidence(service_name="payment", lookback_seconds=300)

    assert bundle.trace_ids == []
    assert bundle.metrics == []
    assert bundle.log_excerpts == []

    metadata = bundle.metadata
    assert metadata["source_status"]["jaeger"] == "unavailable"
    assert metadata["source_status"]["prometheus"] == "unavailable"
    assert metadata["source_status"]["opensearch"] == "unavailable"
    assert metadata["all_sources_available"] is False
    assert metadata["partial_failure"] is True
    assert "Jaeger timed out" in metadata["source_errors"]["jaeger"]
    assert "Prometheus down" in metadata["source_errors"]["prometheus"]
    assert "OpenSearch down" in metadata["source_errors"]["opensearch"]


def test_collect_evidence_custom_topology(mock_jaeger, mock_prometheus, mock_opensearch):
    mock_jaeger.get_error_trace_ids.return_value = []
    mock_prometheus.get_service_metrics.return_value = []
    mock_opensearch.get_error_logs.return_value = []

    custom_topo = {
        "custom-edge": ["custom-worker"],
        "custom-worker": [],
    }

    collector = EvidenceCollector(
        jaeger_client=mock_jaeger,
        prometheus_client=mock_prometheus,
        opensearch_client=mock_opensearch,
        service_topology=custom_topo,
    )

    bundle = collector.collect_evidence(service_name="custom-worker")
    assert bundle.dependency_graph["upstream"] == ["custom-edge"]
    assert bundle.dependency_graph["downstream"] == []
