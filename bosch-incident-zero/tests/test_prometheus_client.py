import json
import pytest
import requests
from unittest.mock import MagicMock

from src.telemetry.prometheus_client import PrometheusClient
from src.telemetry.exceptions import (
    TelemetryConnectionError,
    TelemetryDataError,
    TelemetryResponseError,
    TelemetryTimeoutError,
)


@pytest.fixture
def mock_session():
    return MagicMock(spec=requests.Session)


@pytest.fixture
def client(mock_session):
    return PrometheusClient(base_url="http://mock-prometheus:9090", timeout_seconds=5.0, session=mock_session)


def test_prometheus_health_check_success(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_session.get.return_value = mock_resp

    assert client.health_check() is True
    mock_session.get.assert_called_once_with(
        "http://mock-prometheus:9090/-/healthy",
        timeout=3.0,
    )


def test_prometheus_health_check_failure(client, mock_session):
    mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection refused")
    mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")
    assert client.health_check() is False


def test_prometheus_query_success(client, mock_session):
    payload = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"service_name": "cart"},
                    "value": [1729688400.0, "0.45"],
                }
            ],
        },
    }
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = payload
    mock_session.request.return_value = mock_resp

    res = client.query("up")
    assert res["status"] == "success"
    assert client.query_scalar("up") == 0.45


def test_prometheus_query_range_success(client, mock_session):
    payload = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"service_name": "cart"},
                    "values": [[1729688400, "0.1"], [1729688415, "0.2"]],
                }
            ],
        },
    }
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = payload
    mock_session.request.return_value = mock_resp

    res = client.query_range("rate(http_requests_total[5m])", start=1729688400, end=1729688430)
    assert res["data"]["resultType"] == "matrix"


def test_prometheus_empty_result_returns_none_scalar(client, mock_session):
    payload = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [],
        },
    }
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = payload
    mock_session.request.return_value = mock_resp

    assert client.query_scalar("up{service_name='nonexistent'}") is None


def test_prometheus_api_error_status(client, mock_session):
    payload = {
        "status": "error",
        "errorType": "bad_data",
        "error": "parse error: unexpected identifier",
    }
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = payload
    mock_session.request.return_value = mock_resp

    with pytest.raises(TelemetryResponseError, match="parse error"):
        client.query("invalid syntax promql")


def test_prometheus_connection_error(client, mock_session):
    mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")

    with pytest.raises(TelemetryConnectionError):
        client.query("up")


def test_prometheus_timeout(client, mock_session):
    mock_session.request.side_effect = requests.exceptions.Timeout("Read timeout")

    with pytest.raises(TelemetryTimeoutError):
        client.query("up")


def test_prometheus_http_503(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"
    mock_session.request.return_value = mock_resp

    with pytest.raises(TelemetryResponseError) as exc_info:
        client.query("up")
    assert exc_info.value.status_code == 503


def test_prometheus_malformed_json(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.text = "<html>502 Bad Gateway</html>"
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
    mock_session.request.return_value = mock_resp

    with pytest.raises(TelemetryDataError):
        client.query("up")


def test_prometheus_get_service_metrics(client, mock_session):
    payload = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"service_name": "cart"},
                    "value": [1729688400.0, "0.125"],
                }
            ],
        },
    }
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = payload
    mock_session.request.return_value = mock_resp

    metrics = client.get_service_metrics("cart")
    assert len(metrics) > 0
    assert metrics[0].service == "cart"
    assert metrics[0].metric_name == "error_rate_ratio"
    assert metrics[0].observed_value == 0.125


def test_prometheus_get_service_metrics_uses_span_metrics(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "data": {"resultType": "vector", "result": []}}
    mock_session.request.return_value = mock_resp

    assert client.get_service_metrics("payment") == []
    queries = [c.kwargs["params"]["query"] for c in mock_session.request.call_args_list]
    assert any("traces_span_metrics_calls_total" in q and 'service_name="payment"' in q for q in queries)
    assert not any("http_server_duration_milliseconds" in q for q in queries)


def test_prometheus_get_services_overview(client, mock_session):
    rows = [
        {"metric": {"service_name": "payment"}, "value": [1729688400.0, "0.5"]},
        {"metric": {"service_name": "cart"}, "value": [1729688400.0, "NaN"]},
    ]
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "data": {"resultType": "vector", "result": rows}}
    mock_session.request.return_value = mock_resp

    overview = client.get_services_overview()
    assert overview["payment"] == {"error_rate_ratio": 0.5, "p95_latency_ms": 0.5, "requests_per_second": 0.5}
    assert "cart" not in overview


def test_prometheus_missing_baseline_is_none_not_zero(client, mock_session):
    current = MagicMock(ok=True)
    current.json.return_value = {"status": "success", "data": {"resultType": "vector",
                                 "result": [{"metric": {}, "value": [1.0, "9000"]}]}}
    empty = MagicMock(ok=True)
    empty.json.return_value = {"status": "success", "data": {"resultType": "vector", "result": []}}
    mock_session.request.side_effect = lambda *a, **kw: empty if "offset" in kw["params"]["query"] else current

    metrics = client.get_service_metrics("checkout")
    assert metrics and all(m.baseline_value is None for m in metrics)


def test_prometheus_overview_excludes_infra_services(client, mock_session):
    rows = [{"metric": {"service_name": s}, "value": [1.0, "0.2"]} for s in ("payment", "flagd", "load-generator")]
    mock_resp = MagicMock(ok=True)
    mock_resp.json.return_value = {"status": "success", "data": {"resultType": "vector", "result": rows}}
    mock_session.request.return_value = mock_resp

    assert set(client.get_services_overview()) == {"payment"}
    assert set(client.get_services_overview(include_infra=True)) == {"payment", "flagd", "load-generator"}
