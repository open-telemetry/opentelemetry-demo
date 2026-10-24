from oncall.guard import is_banned_service, is_banned_text, scrub


def test_scrub_removes_nested_feature_flag_data():
    value = {"feature_flag.key": "x", "nested": [{"name": "feature_flag.evaluated"}, {"ok": 1}]}
    assert scrub(value) == {"nested": [{"ok": 1}]}


def test_guard_bans_services_and_text():
    assert is_banned_service("FLAGD")
    assert is_banned_service("flagd-ui")
    assert is_banned_text("request /feature on :8013")
    assert not is_banned_text("payment timeout")
