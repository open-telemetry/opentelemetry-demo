import json
import pytest
import requests
from unittest.mock import MagicMock

from src.telemetry.jaeger_client import JaegerClient
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
    return JaegerClient(base_url="http://mock-jaeger:16686", timeout_seconds=5.0, session=mock_session)


def test_jaeger_health_check_success(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_session.get.return_value = mock_resp

    assert client.health_check() is True
    mock_session.get.assert_called_once_with(
        "http://mock-jaeger:16686/jaeger/ui/api/v3/services",
        timeout=3.0,
    )


def test_jaeger_health_check_failure(client, mock_session):
    mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection refused")
    assert client.health_check() is False


def test_jaeger_get_services_v3_success(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"services": ["ad", "cart", "checkout"]}
    mock_session.request.return_value = mock_resp

    services = client.get_services()
    assert services == ["ad", "cart", "checkout"]


def test_jaeger_get_services_empty(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"services": None}
    mock_session.request.return_value = mock_resp

    services = client.get_services()
    assert services == []


def test_jaeger_get_error_trace_ids_v3(client, mock_session):
    v3_payload = {
        "result": {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "cart"}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "trace-error-001",
                                    "spanId": "span-001",
                                    "name": "CartService.GetCart",
                                    "status": {"code": 2, "message": "Internal error"},
                                },
                                {
                                    "traceId": "trace-ok-002",
                                    "spanId": "span-002",
                                    "name": "CartService.AddItem",
                                    "status": {"code": 1},
                                },
                            ]
                        }
                    ],
                }
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = v3_payload
    mock_session.request.return_value = mock_resp

    trace_ids = client.get_error_trace_ids(service_name="cart")
    assert trace_ids == ["trace-error-001"]


def test_jaeger_get_error_trace_ids_v1_fallback(client, mock_session):
    v1_payload = {
        "data": [
            {
                "traceID": "trace-v1-999",
                "spans": [
                    {
                        "spanID": "s1",
                        "tags": [
                            {"key": "error", "value": True}
                        ],
                    }
                ],
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = v1_payload
    mock_session.request.return_value = mock_resp

    trace_ids = client.get_error_trace_ids(service_name="cart")
    assert trace_ids == ["trace-v1-999"]


def test_jaeger_empty_traces_returns_empty_list(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"result": {"resourceSpans": []}}
    mock_session.request.return_value = mock_resp

    trace_ids = client.get_error_trace_ids(service_name="payment")
    assert trace_ids == []


def test_jaeger_connection_error(client, mock_session):
    mock_session.request.side_effect = requests.exceptions.ConnectionError("Failed to reach host")

    with pytest.raises(TelemetryConnectionError, match="Failed to connect"):
        client.get_traces("cart")


def test_jaeger_timeout(client, mock_session):
    mock_session.request.side_effect = requests.exceptions.Timeout("Request timed out")

    with pytest.raises(TelemetryTimeoutError, match="timed out"):
        client.get_traces("cart")


def test_jaeger_http_500_error(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error in Jaeger"
    mock_session.request.return_value = mock_resp

    with pytest.raises(TelemetryResponseError) as exc_info:
        client.get_traces("cart")
    assert exc_info.value.status_code == 500


def test_jaeger_malformed_json(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.text = "NOT JSON DATA"
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
    mock_session.request.return_value = mock_resp

    with pytest.raises(TelemetryDataError, match="Malformed JSON"):
        client.get_traces("cart")
