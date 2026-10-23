from tools.result import ToolResult
from tools.sanitize import clean, clean_result, is_blocked_name


def test_drops_feature_flag_keys_at_any_depth():
    data = {"a": 1, "feature_flag.key": "x", "attrs": {"feature_flag.variant": "on", "ok": 2}}
    assert clean(data) == {"a": 1, "attrs": {"ok": 2}}


def test_drops_attribute_entries_named_like_flag_keys():
    tags = [{"key": "feature_flag.key", "value": "x"}, {"key": "http.method", "value": "GET"}]
    assert clean({"tags": tags}) == {"tags": [{"key": "http.method", "value": "GET"}]}


def test_drops_items_belonging_to_the_flag_service_and_ui():
    rows = [
        {"service_name": "flagd", "v": 1},
        {"service_name": "flagd-ui", "v": 2},
        {"container_name": "flagd", "v": 3},
        {"name": "/flagd", "v": 4},
        {"name": "opentelemetry-demo-flagd-1", "v": 5},
        {"job": "opentelemetry-demo/flagd", "v": 6},
        {"service_name": "cart", "v": 7},
    ]
    assert clean(rows) == [{"service_name": "cart", "v": 7}]


def test_similar_but_different_names_survive():
    assert not is_blocked_name("flagship")
    assert not is_blocked_name("flag-service")
    assert clean([{"service": "flagship"}]) == [{"service": "flagship"}]


def test_drops_records_with_the_flag_ui_path_in_any_value():
    logs = [
        {"body": "GET /feature/api/read HTTP/1.1 200", "service": "frontend-proxy"},
        {"body": "GET /feature HTTP/1.1 200", "service": "frontend-proxy"},
        {"body": "GET /features HTTP/1.1 200", "service": "frontend-proxy"},
        {"body": "GET /api/cart", "attrs": {"url": "http://x/feature/y"}},
        {"body": "GET /api/cart", "service": "frontend"},
    ]
    kept = clean(logs)
    assert [r["body"] for r in kept] == ["GET /features HTTP/1.1 200", "GET /api/cart"]


def test_poison_stops_at_the_nearest_list_element():
    row = {"service": "cart", "top_error_spans": [{"span_name": "GET /feature/x"}, {"span_name": "ok"}]}
    assert clean([row]) == [{"service": "cart", "top_error_spans": [{"span_name": "ok"}]}]


def test_top_level_dict_loses_only_offending_keys():
    assert clean({"error": "see /feature/ui", "state": "x"}) == {"state": "x"}


def test_clean_result_turns_fully_filtered_data_into_no_data():
    result = ToolResult("query_metrics", "data", ["q"], {}, items=[{"service_name": "flagd"}], total_items=1)
    cleaned = clean_result(result)
    assert cleaned.state == "no_data" and cleaned.items == []
    assert cleaned.state != "data"


def test_clean_does_not_modify_its_input():
    data = [{"service": "flagd"}, {"service": "cart", "feature_flag.x": 1}]
    clean(data)
    assert data == [{"service": "flagd"}, {"service": "cart", "feature_flag.x": 1}]


def test_drops_flag_evaluation_span_names_but_keeps_other_spans():
    spans = [
        {"span_name": "flagd.evaluation.v2.Service/ResolveBoolean", "service": "cart"},
        {"span_name": "feature_flag.evaluation", "service": "cart"},
        {"span_name": "POST /oteldemo.CartService/AddItem", "service": "cart"},
    ]
    assert clean(spans) == [{"span_name": "POST /oteldemo.CartService/AddItem", "service": "cart"}]
