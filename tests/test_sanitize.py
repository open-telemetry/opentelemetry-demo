from tools.result import ToolResult
from tools.sanitize import clean, clean_counted, clean_result, clean_spans, has_flag_text, is_blocked_name


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


# --- OTLP-style attribute lists and events ---------------------------------------------

def otlp(key, value):
    return {"key": key, "value": {"stringValue": value}}


def test_otlp_attribute_lists_lose_flag_entries_including_vendor_prefixed_keys():
    attributes = [otlp("feature_flag.key", "x"), otlp("demo.feature_flag.cache", "on"), otlp("rpc.method", "Charge")]
    assert clean({"attributes": attributes}) == {"attributes": [otlp("rpc.method", "Charge")]}


def test_otlp_events_named_for_flags_are_dropped_whole_and_others_kept():
    events = [
        {"name": "feature_flag.evaluation", "attributes": [otlp("feature_flag.result.variant", "on")]},
        {"name": "feature_flag", "attributes": []},
        {"name": "exception", "attributes": [otlp("exception.type", "Boom")]},
    ]
    assert clean({"events": events})["events"] == [{"name": "exception", "attributes": [otlp("exception.type", "Boom")]}]


def test_plain_dict_attributes_are_still_handled_the_same_way():
    assert clean({"attributes": {"feature_flag.key": "x", "demo.feature_flag.y": 1, "keep": 2}}) == {"attributes": {"keep": 2}}


# --- text rule ------------------------------------------------------------------------

def test_text_rule_matches_the_flag_system_in_any_case_and_spelling():
    for text in ("connect to flagd failed", "FLAGD", "flagd-ui", "evaluating feature_flag x", "Feature Flag on", "FEATURE_FLAG",
                 "OpenFeature provider", "GET /feature/api HTTP/1.1"):
        assert has_flag_text(text), text
    for text in ("flagship store", "features list", "GET /features", "cart failed", "", None, 5):
        assert not has_flag_text(text), text


def test_text_rule_drops_the_record_and_counts_it():
    cleaned, removed = clean_counted([{"body": "ok"}, {"body": "flagd unreachable"}, {"body": "OpenFeature error"}])
    assert cleaned == [{"body": "ok"}] and removed == 2


def test_counts_do_not_double_count_keys_inside_a_dropped_record():
    cleaned, removed = clean_counted([{"feature_flag.a": 1, "body": "flagd"}, {"body": "ok"}])
    assert cleaned == [{"body": "ok"}] and removed == 1


def test_clean_result_reports_how_many_items_it_removed_but_not_what():
    result = ToolResult("query_logs", "data", ["q"], {}, items=[{"body": "flagd down"}, {"body": "ok"}], total_items=2)
    cleaned = clean_result(result)
    assert cleaned.items == [{"body": "ok"}] and "1 items removed by sanitiser" in cleaned.notes
    assert "flagd" not in str(cleaned.to_dict())


# --- spans ----------------------------------------------------------------------------

def span(name="op", service="cart", scope="scope", attrs=(), events=(), status=None):
    return {"service": service, "scope": scope, "name": name, "attributes": list(attrs), "events": list(events), "status": status or {}}


def test_clean_spans_drops_evaluation_spans_their_http_leg_and_the_flag_service():
    spans = [
        span("flagd.evaluation.v2.Service/ResolveBoolean", scope="OpenTelemetry.Instrumentation.GrpcNetClient"),
        span("POST", scope="System.Net.Http", attrs=[otlp("server.address", "flagd"), otlp("url.full", "http://flagd:8013/x")]),
        span("resolveBoolean", service="flagd", scope="jsonEvaluator"),
        span("POST", service="frontend-proxy", attrs=[otlp("http.url", "http://frontend-proxy:8080/feature/api/read")]),
        span("POST /oteldemo.CartService/GetCart"),
    ]
    kept, removed = clean_spans(spans)
    assert [s["name"] for s in kept] == ["POST /oteldemo.CartService/GetCart"] and removed == 4


def test_clean_spans_keeps_an_ordinary_client_span_to_another_service():
    ordinary = span("POST", scope="System.Net.Http", attrs=[otlp("server.address", "payment"), otlp("url.full", "http://payment:8080/charge")])
    assert clean_spans([ordinary]) == ([ordinary], 0)


def test_clean_spans_strips_flag_attributes_and_events_but_keeps_the_span():
    s = span("get_product_list", attrs=[otlp("demo.feature_flag.recommendation_cache", "on"), otlp("app.products.count", "9")],
             events=[{"name": "feature_flag", "attributes": [otlp("feature_flag.key", "k")]},
                     {"name": "exception", "attributes": [otlp("exception.type", "Boom"), otlp("feature_flag.key", "k")]}])
    kept, removed = clean_spans([s])
    assert kept[0]["attributes"] == [otlp("app.products.count", "9")]
    assert kept[0]["events"] == [{"name": "exception", "attributes": [otlp("exception.type", "Boom")]}]
    assert removed == 3


def test_a_status_message_or_exception_text_that_names_the_flag_system_is_blanked_not_the_span():
    s = span("charge", status={"code": 2, "message": "flagd provider not ready"},
             events=[{"name": "exception", "attributes": [otlp("exception.message", "OpenFeature failure"), otlp("exception.type", "Error")]}])
    kept, removed = clean_spans([s])
    assert kept[0]["status"] == {"code": 2}  # still an error, just without the message
    assert kept[0]["events"][0]["attributes"] == [otlp("exception.type", "Error")]
    assert removed == 2


def test_clean_spans_does_not_modify_its_input():
    s = span("x", attrs=[otlp("feature_flag.key", "k")], status={"code": 2, "message": "flagd"})
    before = repr(s)
    clean_spans([s])
    assert repr(s) == before
