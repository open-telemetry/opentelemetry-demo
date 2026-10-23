import json
import pytest
import requests
from unittest.mock import MagicMock

from src.telemetry.opensearch_client import OpenSearchClient
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
    return OpenSearchClient(base_url="http://mock-opensearch:9200", timeout_seconds=5.0, session=mock_session)


def test_opensearch_health_check_green(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "green"}
    mock_session.get.return_value = mock_resp

    assert client.health_check() is True


def test_opensearch_health_check_failure(client, mock_session):
    mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection refused")
    assert client.health_check() is False


def test_opensearch_get_error_logs_dsl_success(client, mock_session):
    dsl_payload = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                {
                    "_source": {
                        "observedTimestamp": "2026-10-23T14:10:00Z",
                        "severityText": "ERROR",
                        "body": "Connection refused to Valkey instance at valkey-cart:6379",
                        "traceId": "trace-valkey-fail-001",
                    }
                },
                {
                    "_source": {
                        "observedTimestamp": "2026-10-23T14:10:05Z",
                        "severityText": "FATAL",
                        "body": "Unhandled exception in GetCartHandler",
                    }
                },
            ],
        }
    }
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = dsl_payload
    mock_session.request.return_value = mock_resp

    logs = client.get_error_logs(service_name="cart")
    assert len(logs) == 2
    assert "Connection refused to Valkey" in logs[0]
    assert "[traceId=trace-valkey-fail-001]" in logs[0]
    assert "Unhandled exception in GetCartHandler" in logs[1]


def test_opensearch_get_error_logs_ppl_fallback(client, mock_session):
    # First request (DSL search) fails, triggering PPL fallback
    dsl_fail = MagicMock()
    dsl_fail.ok = False
    dsl_fail.status_code = 400
    dsl_fail.text = "Unknown index"

    ppl_success = MagicMock()
    ppl_success.ok = True
    ppl_success.json.return_value = {
        "schema": [
            {"name": "observedTimestamp", "type": "string"},
            {"name": "severityText", "type": "string"},
            {"name": "body", "type": "string"},
            {"name": "traceId", "type": "string"},
        ],
        "datarows": [
            [
                "2026-10-23T14:12:00Z",
                "ERROR",
                "PPL fallback detected error",
                "trace-ppl-777",
            ]
        ],
    }

    mock_session.request.side_effect = [
        requests.exceptions.HTTPError(response=dsl_fail),
        ppl_success,
    ]

    logs = client.get_error_logs(service_name="cart")
    assert len(logs) == 1
    assert "PPL fallback detected error" in logs[0]
    assert "[traceId=trace-ppl-777]" in logs[0]


def test_opensearch_empty_hits(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"hits": {"total": {"value": 0}, "hits": []}}
    mock_session.request.return_value = mock_resp

    logs = client.get_error_logs(service_name="email")
    assert logs == []


def test_opensearch_connection_error(client, mock_session):
    mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")

    with pytest.raises(TelemetryConnectionError):
        client.search()


def test_opensearch_timeout(client, mock_session):
    mock_session.request.side_effect = requests.exceptions.Timeout("Timeout")

    with pytest.raises(TelemetryTimeoutError):
        client.search()


def test_opensearch_http_404(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 404
    mock_resp.text = '{"error": "index_not_found_exception"}'
    mock_session.request.return_value = mock_resp

    with pytest.raises(TelemetryResponseError) as exc_info:
        client.search()
    assert exc_info.value.status_code == 404


def test_opensearch_malformed_json(client, mock_session):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.text = "NOT JSON"
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
    mock_session.request.return_value = mock_resp

    with pytest.raises(TelemetryDataError):
        client.search()
