"""Unit tests for oncall telemetry backends."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from oncall.tools.backends import (
    BackendError,
    LiveBackend,
    OfflineBackend,
    RecordingBackend,
    TelemetryBackend,
    get_backend,
    make_request_hash,
)
from oncall.tools.record import record_scenario


def test_protocol_conformance() -> None:
    live = LiveBackend()
    offline = OfflineBackend()
    recording = RecordingBackend()

    assert isinstance(live, TelemetryBackend)
    assert isinstance(offline, TelemetryBackend)
    assert isinstance(recording, TelemetryBackend)


def test_make_request_hash_deterministic() -> None:
    h1 = make_request_hash("prom_query", {"promql": "up", "at": None})
    h2 = make_request_hash("prom_query", {"promql": "up", "at": None})
    h3 = make_request_hash("prom_query", {"at": None, "promql": "up"})  # key order diff
    h4 = make_request_hash("prom_query", {"promql": "down", "at": None})

    assert h1 == h2
    assert h1 == h3
    assert h1 != h4


def test_live_backend_prom_query_success() -> None:
    backend = LiveBackend(prom_url="http://prometheus:9090")
    fake_data = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"__name__": "up", "instance": "demo:8080"},
                    "value": [1600000000, "1"],
                }
            ],
        },
    }

    with patch.object(backend, "_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = fake_data
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        res = backend.prom_query("up")
        assert res == fake_data
        mock_client.get.assert_called_once_with(
            "http://prometheus:9090/api/v1/query",
            params={"query": "up"},
        )


def test_live_backend_unreachable_raises_backend_error() -> None:
    backend = LiveBackend(prom_url="http://invalid-host-prom:9090")

    with patch.object(backend, "_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__enter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        with pytest.raises(BackendError) as exc_info:
            backend.prom_query("up")
        assert "unreachable" in str(exc_info.value).lower()


def test_recording_and_offline_roundtrip(tmp_path: Path) -> None:
    scenario = "test_scenario"
    rec_backend = RecordingBackend(
        scenario=scenario,
        fixtures_dir=tmp_path,
        prom_url="http://fake-prom:9090",
        jaeger_url="http://fake-jaeger:16686",
    )

    fake_prom_res = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [{"metric": {"service_name": "checkout"}, "value": [123, "1"]}],
        },
    }
    fake_jaeger_services = ["checkout", "cart", "frontend"]

    with patch.object(rec_backend, "_client") as mock_client_factory:
        mock_client = MagicMock()
        prom_resp = MagicMock(status_code=200)
        prom_resp.json.return_value = fake_prom_res

        jaeger_resp = MagicMock(status_code=200)
        jaeger_resp.json.return_value = {"data": fake_jaeger_services}

        def mock_get(url: str, **kwargs: object) -> MagicMock:
            if "query" in url:
                return prom_resp
            if "services" in url:
                return jaeger_resp
            return MagicMock(status_code=404)

        mock_client.get.side_effect = mock_get
        mock_client.__enter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        # Record calls
        res1 = rec_backend.prom_query("up")
        assert res1 == fake_prom_res
        res2 = rec_backend.jaeger_services()
        assert res2 == fake_jaeger_services

    # Now verify OfflineBackend reading from the recorded directory
    offline_backend = OfflineBackend(scenario=scenario, fixtures_dir=tmp_path)
    replayed_prom = offline_backend.prom_query("up")
    assert replayed_prom == fake_prom_res

    replayed_jaeger = offline_backend.jaeger_services()
    assert replayed_jaeger == fake_jaeger_services

    # Unknown query should return empty default without crashing
    unknown_prom = offline_backend.prom_query("unknown_metric")
    assert unknown_prom["status"] == "success"
    assert unknown_prom["data"]["result"] == []

    unknown_traces = offline_backend.jaeger_traces(service="unknown_service")
    assert unknown_traces == []


def test_get_backend_modes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TELEMETRY_BACKEND", "live")
    assert isinstance(get_backend(), LiveBackend)

    monkeypatch.setenv("TELEMETRY_BACKEND", "offline")
    monkeypatch.setenv("OFFLINE_DIR", str(tmp_path))
    assert isinstance(get_backend(), OfflineBackend)

    monkeypatch.setenv("TELEMETRY_BACKEND", "record")
    assert isinstance(get_backend(), RecordingBackend)


def test_record_scenario_cli(tmp_path: Path) -> None:
    rec_backend = RecordingBackend(
        scenario="mock_incident",
        fixtures_dir=tmp_path,
    )
    with (
        patch.object(
            rec_backend,
            "prom_query",
            return_value={"status": "success", "data": {"result": []}},
        ),
        patch.object(rec_backend, "jaeger_services", return_value=["checkout"]),
        patch.object(rec_backend, "jaeger_traces", return_value=[]),
        patch.object(rec_backend, "logs_search", return_value=[]),
    ):
        count = record_scenario(scenario="mock_incident", backend=rec_backend)
        assert count > 0
