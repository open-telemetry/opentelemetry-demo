from app.allowlist import (
    FLAG_SERVICE_MAP,
    RESTART_ALLOWLIST,
    RESTART_BLOCKLIST,
    RUNBOOK_FLAGS,
    get_action_service,
    is_flag_allowed,
    is_service_restart_allowed,
    is_throttle_allowed,
)


def test_allowed_services_restart() -> None:
    for svc in RESTART_ALLOWLIST:
        ok, reason = is_service_restart_allowed(svc)
        assert ok, f"Expected {svc} to be allowed, but got: {reason}"


def test_blocklisted_services_restart() -> None:
    for svc in RESTART_BLOCKLIST:
        ok, reason = is_service_restart_allowed(svc)
        assert not ok, f"Expected {svc} to be blocked"
        assert "protected and cannot be restarted" in reason


def test_arbitrary_unlisted_service_restart() -> None:
    unlisted = ["random-service", "nginx", "redis-master", "custom-app"]
    for svc in unlisted:
        ok, reason = is_service_restart_allowed(svc)
        assert not ok
        assert "not in the restart allowlist" in reason


def test_empty_or_invalid_service_restart() -> None:
    ok, _ = is_service_restart_allowed("")
    assert not ok
    ok, _ = is_service_restart_allowed(None)  # type: ignore[arg-type]
    assert not ok


def test_allowed_runbook_flags_off_variant() -> None:
    for flag in RUNBOOK_FLAGS:
        ok, reason = is_flag_allowed(flag, "off")
        assert ok, f"Expected {flag}=off to be allowed, got: {reason}"


def test_disallowed_flag_variants() -> None:
    disallowed_variants = ["on", "100%", "50%", "10sec", "5sec", "100x", "true", "enabled"]
    for var in disallowed_variants:
        ok, reason = is_flag_allowed("paymentFailure", var)
        assert not ok
        assert "Only off/default variant is allowed" in reason


def test_unlisted_flags() -> None:
    unlisted = ["unrecognizedFlag", "debugMode", "superSlowMode", "secretBackdoor"]
    for flag in unlisted:
        ok, reason = is_flag_allowed(flag, "off")
        assert not ok
        assert "not in runbook flag list" in reason


def test_throttle_allowlist_validation() -> None:
    ok, _ = is_throttle_allowed(users=5, spawn_rate=1.0)
    assert ok
    ok, _ = is_throttle_allowed(users=1, spawn_rate=0.5)
    assert ok

    ok, reason = is_throttle_allowed(users=0, spawn_rate=1.0)
    assert not ok
    assert "users must be >= 1" in reason

    ok, reason = is_throttle_allowed(users=-1, spawn_rate=1.0)
    assert not ok

    ok, reason = is_throttle_allowed(users=5, spawn_rate=0.0)
    assert not ok
    assert "spawn_rate must be >= 0.1" in reason


def test_get_action_service() -> None:
    assert get_action_service("restart_service", {"service": "payment"}) == "payment"
    assert get_action_service("set_feature_flag", {"flag": "paymentFailure"}) == "payment"
    assert get_action_service("set_feature_flag", {"flag": "adHighCpu"}) == "ad"
    assert get_action_service("set_feature_flag", {"flag": "cartFailure"}) == "cart"
    assert get_action_service("throttle_load_generator", {"users": 2}) == "load-generator"
    assert get_action_service("scale_service", {"service": "payment"}) == "payment"
    assert get_action_service("rollback", {}) == "rollback"
