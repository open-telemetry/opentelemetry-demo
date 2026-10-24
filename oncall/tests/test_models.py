from oncall.models import (
    FLAG_REDACTED,
    MAX_EVIDENCE_ITEMS,
    MAX_SUMMARY_CHARS,
    llm_view,
    make_error,
    make_result,
    scrub_flags,
)
from oncall.tools import TOOL_SCHEMAS, TOOLS, register_tool


def _evidence(i: int) -> dict:
    return {"id": f"log:cart@2026-10-23T10:00:{i:02d}Z", "text": "boom", "ts": None}


def test_make_result_happy_path():
    result = make_result("get_metrics", {"service": "cart"}, "ok", [_evidence(1)])
    assert result == {
        "tool": "get_metrics",
        "query": {"service": "cart"},
        "summary": "ok",
        "evidence": [_evidence(1)],
        "ok": True,
        "error": None,
    }


def test_make_result_truncates_summary_and_evidence():
    result = make_result("t", {}, "x" * 5000, [_evidence(i) for i in range(50)])
    assert len(result["summary"]) == MAX_SUMMARY_CHARS
    assert len(result["evidence"]) == MAX_EVIDENCE_ITEMS


def test_make_error():
    result = make_error("t", {"a": 1}, "timeout")
    assert result["ok"] is False
    assert result["error"] == "timeout"
    assert result["evidence"] == []


def test_scrub_flags_removes_keys_and_text_lines():
    result = make_result(
        "get_metrics",
        {"service": "payment", "labels": {"feature_flag_key": "paymentFailure"}},
        "payment error_rate 0.31\nfeature_flag_key=paymentFailure variant=on",
        [
            {
                "id": "metric:q@2026-10-23T10:00:00Z",
                "text": 'rate{feature_flag_key="paymentFailure"} 1.0',
                "ts": None,
            },
            {"id": "log:cart@2026-10-23T10:00:01Z", "text": "boom", "ts": None},
        ],
    )
    result["query"]["span"] = {
        "attributes": {
            "feature_flag.result.value": True,
            "demo.Feature_Flag.recommendation_cache": "on",
            "rpc.method": "Charge",
        },
        "otlp": [
            {"key": "feature_flag.key", "value": {"stringValue": "paymentFailure"}},
            {"key": "rpc.method", "value": {"stringValue": "Charge"}},
        ],
    }

    scrubbed = scrub_flags(result)

    assert scrubbed["query"] == {
        "service": "payment",
        "labels": {},
        "span": {
            "attributes": {"rpc.method": "Charge"},
            "otlp": [{"key": "rpc.method", "value": {"stringValue": "Charge"}}],
        },
    }
    assert scrubbed["summary"] == f"payment error_rate 0.31\n{FLAG_REDACTED} variant=on"
    assert scrubbed["evidence"][0]["text"] == f"{FLAG_REDACTED} 1.0"
    assert scrubbed["evidence"][1]["text"] == "boom"
    assert "paymentFailure" not in str(scrubbed)


def test_scrub_flags_drops_camel_case_keys_at_any_depth():
    data = {"a": 1, "feature_flag": "x", "nested": [{"FeatureFlag.name": "y", "b": 2}]}
    assert scrub_flags(data) == {"a": 1, "nested": [{"b": 2}]}


def test_scrub_flags_leaves_clean_values_unchanged():
    result = make_result("t", {"service": "cart", "n": 3}, "ok", [_evidence(1)])
    assert scrub_flags(result) == result
    assert scrub_flags(None) is None


def test_registered_tool_result_is_scrubbed():
    @register_tool("dummy_flags", "Leaks flag data.", {"properties": {}})
    def dummy_flags():
        return make_result(
            "dummy_flags", {"feature_flag_key": "x"}, "feature_flag_key=x", []
        )

    try:
        result = TOOLS["dummy_flags"]()
    finally:
        TOOLS.pop("dummy_flags", None)
        TOOL_SCHEMAS.pop("dummy_flags", None)
    assert result["query"] == {}
    assert result["summary"] == FLAG_REDACTED


def test_llm_view_hides_raw_promql_only():
    result = make_result("t", {"metric": "rps", "promql": "sum(x)"}, "ok", [])
    assert llm_view(result)["query"] == {"metric": "rps"}
    assert result["query"]["promql"] == "sum(x)"


def test_every_registered_tool_goes_through_the_scrubbing_wrapper():
    import oncall.platform.containers
    import oncall.platform.deploys  # noqa: F401

    wrapper_code = {fn.__code__ for fn in TOOLS.values()}
    assert len(wrapper_code) == 1
    assert {"container_health", "deploy_history", "get_metrics"} <= TOOLS.keys()
    assert all(hasattr(fn, "__wrapped__") for fn in TOOLS.values())
