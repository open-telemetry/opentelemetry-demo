from fastapi.testclient import TestClient
import pytest

from app.audit import killswitch
from app.main import ACTION_API_SECRET, app
from app.token_auth import mint_approval_token

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_killswitch() -> None:
    killswitch.set_engaged(False)


def test_health_endpoint() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "action-api"}


def test_killswitch_endpoints() -> None:
    resp = client.get("/killswitch")
    assert resp.status_code == 200
    assert resp.json() == {"engaged": False}

    resp = client.post("/killswitch", json={"engaged": True})
    assert resp.status_code == 200
    assert resp.json() == {"engaged": True}

    resp = client.get("/killswitch")
    assert resp.status_code == 200
    assert resp.json() == {"engaged": True}

    client.post("/killswitch", json={"engaged": False})


def test_dry_run_needs_no_token() -> None:
    resp = client.post(
        "/actions",
        json={
            "action": "restart_service",
            "params": {"service": "payment"},
            "incident_id": "INC-TEST-1",
            "dry_run": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("dry_run") is True
    assert data.get("status") == "would_apply"
    assert "Would restart service 'payment'" in data.get("summary", "")


def test_mutating_action_without_token_returns_403() -> None:
    resp = client.post(
        "/actions",
        json={
            "action": "restart_service",
            "params": {"service": "payment"},
            "incident_id": "INC-TEST-2",
            "dry_run": False,
        },
    )
    assert resp.status_code == 403
    assert "Approval token is required" in resp.json().get("detail", "")


def test_allowlist_rejection_returns_400() -> None:
    token = mint_approval_token(
        ACTION_API_SECRET,
        "INC-TEST-3",
        "restart_service",
        {"service": "otel-collector"},
    )
    resp = client.post(
        "/actions",
        json={
            "action": "restart_service",
            "params": {"service": "otel-collector"},
            "incident_id": "INC-TEST-3",
            "approval_token": token,
            "dry_run": False,
        },
    )
    assert resp.status_code == 400
    assert "protected and cannot be restarted" in resp.json().get("detail", "")


def test_killswitch_returns_423_on_mutating_actions() -> None:
    client.post("/killswitch", json={"engaged": True})

    token = mint_approval_token(
        ACTION_API_SECRET,
        "INC-TEST-4",
        "restart_service",
        {"service": "payment"},
    )
    resp = client.post(
        "/actions",
        json={
            "action": "restart_service",
            "params": {"service": "payment"},
            "incident_id": "INC-TEST-4",
            "approval_token": token,
            "dry_run": False,
        },
    )
    assert resp.status_code == 423
    assert "Kill switch is engaged" in resp.json().get("detail", "")

    client.post("/killswitch", json={"engaged": False})


def test_scale_service_returns_unsupported() -> None:
    resp = client.post(
        "/actions",
        json={
            "action": "scale_service",
            "params": {"service": "payment", "replicas": 3},
            "dry_run": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "unsupported"
    assert "Kubernetes only" in data.get("reason", "")


def test_audit_endpoint() -> None:
    resp = client.get("/audit?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert isinstance(data["records"], list)
