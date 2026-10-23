import time

from app.token_auth import mint_approval_token, verify_approval_token

SECRET = "test-secret-key-12345"


def test_mint_and_verify_valid_token() -> None:
    incident_id = "INC-101"
    action = "restart_service"
    params = {"service": "payment"}

    token = mint_approval_token(SECRET, incident_id, action, params, ttl_seconds=300)
    assert ":" in token

    ok, reason = verify_approval_token(SECRET, token, incident_id, action, params)
    assert ok, f"Token verification failed: {reason}"
    assert reason == ""


def test_expired_token_rejected() -> None:
    incident_id = "INC-102"
    action = "set_feature_flag"
    params = {"flag": "paymentFailure", "variant": "off"}

    # Token with ttl of -10 seconds (expired in the past)
    token = mint_approval_token(SECRET, incident_id, action, params, ttl_seconds=-10)

    ok, reason = verify_approval_token(SECRET, token, incident_id, action, params)
    assert not ok
    assert "Token expired" in reason


def test_mismatched_action_rejected() -> None:
    incident_id = "INC-103"
    token = mint_approval_token(SECRET, incident_id, "restart_service", {"service": "payment"})

    ok, reason = verify_approval_token(SECRET, token, incident_id, "set_feature_flag", {"service": "payment"})
    assert not ok
    assert "signature mismatch" in reason


def test_mismatched_params_rejected() -> None:
    incident_id = "INC-104"
    token = mint_approval_token(SECRET, incident_id, "restart_service", {"service": "payment"})

    ok, reason = verify_approval_token(SECRET, token, incident_id, "restart_service", {"service": "cart"})
    assert not ok
    assert "signature mismatch" in reason


def test_mismatched_incident_id_rejected() -> None:
    token = mint_approval_token(SECRET, "INC-105", "restart_service", {"service": "payment"})

    ok, reason = verify_approval_token(SECRET, token, "INC-999", "restart_service", {"service": "payment"})
    assert not ok
    assert "signature mismatch" in reason


def test_wrong_secret_rejected() -> None:
    token = mint_approval_token("different-secret", "INC-106", "restart_service", {"service": "payment"})

    ok, reason = verify_approval_token(SECRET, token, "INC-106", "restart_service", {"service": "payment"})
    assert not ok
    assert "signature mismatch" in reason


def test_missing_or_empty_token_rejected() -> None:
    ok, reason = verify_approval_token(SECRET, "", "INC-107", "restart_service", {})
    assert not ok
    assert "Approval token is required" in reason

    ok, reason = verify_approval_token(SECRET, None, "INC-107", "restart_service", {})
    assert not ok


def test_raw_signature_with_exp_override() -> None:
    incident_id = "INC-108"
    action = "throttle_load_generator"
    params = {"users": 2, "spawn_rate": 1.0}
    exp = int(time.time()) + 300

    token = mint_approval_token(SECRET, incident_id, action, params, ttl_seconds=300)
    raw_sig = token.split(":", 1)[1]

    ok, reason = verify_approval_token(SECRET, raw_sig, incident_id, action, params, exp_override=exp)
    assert ok, f"Expected raw sig with exp_override to succeed, got: {reason}"
