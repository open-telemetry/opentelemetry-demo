import json
import json as jsonlib  # FakeHttp.__call__ has a parameter named json, like requests.post

import pytest
import requests

from tools.logs import MAX_MESSAGE, build_query, group, query_logs, to_records


def hit(body, service="payment", level="warn", ts="2026-10-23T17:59:56.975560089Z", trace="abc123", nested=True, **extra):
    """A hit shaped like the live documents: dotted keys inside the `resource` and `severity` objects."""
    source = {
        "body": body,
        "observedTimestamp": ts,
        "resource": {"service.name": service, "host.name": "docker-desktop"} if nested else {},
        "severity": {"text": level} if level else {},
        "traceId": trace,
        "spanId": "def456",
        **extra,
    }
    if not nested:
        source["resource.service.name"] = service
    return {"_index": "otel-logs-2026-10-23", "_source": source}


def answer(hits, total=None, **kw):
    return {"took": 3, "timed_out": False, "_shards": {"total": 1, "failed": 0}, **kw,
            "hits": {"total": {"value": len(hits) if total is None else total, "relation": "eq"}, "hits": hits}}


class FakeHttp:
    def __init__(self, body=None, status=200, raises=None, text=None):
        self.body, self.status, self.raises, self.text, self.calls = body, status, raises, text, []

    def __call__(self, url, json, timeout):
        self.calls.append((url, json))
        if self.raises:
            raise self.raises
        response = requests.Response()
        response.status_code = self.status
        response._content = (self.text if self.text is not None else jsonlib.dumps(self.body)).encode()
        return response


def run(http, **kw):
    return query_logs(base_url="http://os.test", http_post=http, **kw)


# --- parsing and grouping -------------------------------------------------------------

def test_fields_are_read_from_nested_dotted_or_mixed_documents():
    records = to_records([hit("a"), hit("b", nested=False), hit("c", level="")])
    assert [r["service"] for r in records] == ["payment", "payment", "payment"]
    assert records[2]["level"] == "none" and records[0]["level"] == "warn"


def test_levels_of_any_case_are_normalised_for_display_only():
    assert to_records([hit("x", level="ERROR")])[0]["level"] == "error"
    assert to_records([hit("x", level="Information")])[0]["level"] == "information"


def test_group_counts_identical_messages_and_keeps_first_last_and_a_trace():
    lines = [  # newest first, as OpenSearch returns them
        hit("boom", ts="2026-10-23T10:00:03.500Z", trace=None),
        hit("boom", ts="2026-10-23T10:00:02.100000000Z", trace="t-new"),
        hit("boom", ts="2026-10-23T10:00:01.000Z", trace="t-old"),
        hit("other", ts="2026-10-23T10:00:00.000Z"),
    ]
    groups = group(to_records(lines))
    boom = groups[0]
    assert boom["message"] == "boom" and boom["count"] == 3
    assert boom["first_seen"] == "2026-10-23T10:00:01.000Z" and boom["last_seen"] == "2026-10-23T10:00:03.500Z"
    assert boom["sample_trace_id"] == "t-new"
    assert groups[1]["message"] == "other"


def test_same_message_from_two_services_stays_two_groups():
    groups = group(to_records([hit("down", service="cart"), hit("down", service="payment")]))
    assert sorted(g["service"] for g in groups) == ["cart", "payment"]


def test_message_text_is_verbatim_including_odd_characters():
    text = "  Payment request failed.\tInvalid token. loyalty_level=gold ✓ \"quoted\" \\n literal  "
    result = run(FakeHttp(answer([hit(text)])))
    assert result.items[0]["message"] == text
    assert json.loads(json.dumps(result.items[0]))["message"] == text


def test_a_very_long_message_is_cut_and_flagged():
    result = run(FakeHttp(answer([hit("x" * (MAX_MESSAGE + 50))])))
    assert len(result.items[0]["message"]) == MAX_MESSAGE and result.items[0]["truncated"] is True


# --- the query ------------------------------------------------------------------------

def test_query_matches_levels_case_insensitively_and_clear_errors_of_any_level():
    body = build_query("2026-01-01T00:00:00+00:00", "2026-01-01T00:10:00+00:00", None, ["x"])
    should = body["query"]["bool"]["filter"][1]["bool"]["should"]
    levels = should[0]["terms"]["severity.text"]
    assert {"error", "fatal", "critical"} <= set(levels) and all(level == level.lower() for level in levels)
    assert "match" in should[1] and "body" in should[1]["match"]  # error text with an info-like level
    assert body["query"]["bool"]["must_not"][0]["terms"]["resource.service.name.keyword"] == ["x"]


def test_the_recorded_query_hides_the_excluded_service_names_but_the_sent_one_has_them():
    http = FakeHttp(answer([hit("boom")]))
    result = run(http, service="payment", window_minutes=7, limit=3)
    sent = json.dumps(http.calls[0][1])
    assert "flagd" in sent
    recorded = " ".join(result.query)
    assert "flagd" not in recorded and "excluded by the sanitiser" in recorded
    assert "otel-logs-*" in recorded and '"payment"' in recorded.replace("'", '"')
    assert result.window["minutes"] == 7


# --- states ---------------------------------------------------------------------------

def test_data():
    result = run(FakeHttp(answer([hit("boom"), hit("boom")], total=250)))
    assert result.state == "data" and result.items[0]["count"] == 2
    assert any("250" in n for n in result.notes)


def test_no_lines_is_no_data_with_a_not_healthy_note():
    result = run(FakeHttp(answer([])))
    assert result.state == "no_data" and result.items == []
    assert any("NOT a healthy signal" in n for n in result.notes)


@pytest.mark.parametrize("http", [
    FakeHttp(raises=requests.exceptions.ConnectionError("refused")),
    FakeHttp(raises=requests.exceptions.ReadTimeout("slow")),
    FakeHttp(status=500, text="boom"),
    FakeHttp(status=400, text='{"error":{"type":"parsing_exception"}}'),
    FakeHttp(text="<html>"),
    FakeHttp({"unexpected": True}),
    FakeHttp(answer([]) | {"_shards": {"total": 3, "failed": 1}}),
    FakeHttp(answer([], timed_out=True)),
])
def test_backend_problems_are_backend_error_never_no_data(http):
    result = run(http)
    assert result.state == "backend_error" and result.error and result.items == []


def test_unknown_opensearch_address_is_backend_error(monkeypatch):
    from tools import logs
    from tools.endpoints import Endpoint
    monkeypatch.setattr(logs, "get_endpoints", lambda: {"opensearch": Endpoint("opensearch", None, "docker port", "no such container")})
    result = query_logs()
    assert result.state == "backend_error" and "no such container" in result.error


def test_bad_arguments_raise():
    for kw in ({"window_minutes": 0}, {"limit": 0}, {"limit": 999}, {"service": "a b"}):
        with pytest.raises(ValueError):
            run(FakeHttp(answer([])), **kw)


# --- sanitising -----------------------------------------------------------------------

def test_lines_mentioning_the_flag_system_are_dropped_and_counted_not_shown():
    hits = [
        hit("failed to connect to flagd: connection refused", service="cart"),
        hit("OpenFeature provider error", service="cart"),
        hit("evaluating Feature_Flag cartFailure", service="cart"),
        hit("the feature flag is on", service="cart"),
        hit("GET /feature/api/read HTTP/1.1 500", service="frontend-proxy", level=""),
        hit("Connection failed. Disposing the object", service="cart", level="Information"),
    ]
    result = run(FakeHttp(answer(hits)))
    assert [g["message"] for g in result.items] == ["Connection failed. Disposing the object"]
    assert "5 items removed by sanitiser" in result.notes
    text = json.dumps([result.items, result.notes]).lower()  # not the query: its word list has "refused"
    assert "openfeature" not in text and "cartfailure" not in text and "/feature" not in text and "refused" not in text


def test_if_every_line_is_removed_the_result_is_no_data():
    result = run(FakeHttp(answer([hit("flagd is unreachable")])))
    assert result.state == "no_data"


def test_asking_for_the_flag_service_makes_no_request():
    http = FakeHttp(answer([hit("x")]))
    result = run(http, service="flagd")
    assert result.state == "no_data" and http.calls == []
