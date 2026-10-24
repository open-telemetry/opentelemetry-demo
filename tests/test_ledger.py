import json

from tools.ledger import Ledger
from tools.result import ToolResult, window_dict, utc_now


def make_result(items=None):
    items = items if items is not None else [{"service": "cart", "error_rate_pct": 1.5}]
    return ToolResult("query_metrics", "data", ["promql"], window_dict(5, utc_now()), items=items, total_items=len(items))


def test_ids_are_prefixed_by_tool_and_count_up_per_tool():
    ledger = Ledger()
    ids = [
        ledger.add("query_metrics", {"window_minutes": 5}, make_result()).id,
        ledger.add("container_health", {}, make_result()).id,
        ledger.add("query_metrics", {}, make_result()).id,
        ledger.add("something_new", {}, make_result()).id,
    ]
    assert ids == ["M1", "C1", "M2", "X1"]


def test_entry_records_tool_arguments_query_window_and_timestamp():
    ledger = Ledger()
    entry = ledger.add("query_metrics", {"top_n": 3}, make_result())
    assert entry.tool == "query_metrics" and entry.arguments == {"top_n": 3}
    assert entry.query == ["promql"] and entry.window["minutes"] == 5
    assert entry.timestamp.endswith("+00:00")
    assert ledger.get("M1") is entry and ledger.get("M9") is None
    assert [e.id for e in ledger.list()] == ["M1"]


def test_results_are_sanitised_on_the_way_in():
    ledger = Ledger()
    entry = ledger.add("query_metrics", {}, make_result([{"service": "flagd"}, {"service": "cart"}]))
    assert entry.result["items"] == [{"service": "cart"}]


def test_save_writes_json_that_round_trips(tmp_path):
    ledger = Ledger()
    ledger.add("query_metrics", {}, make_result())
    ledger.add("container_health", {}, make_result())
    path = ledger.save(tmp_path / "sub" / "ledger.json")
    saved = json.loads(path.read_text())
    assert [e["id"] for e in saved] == ["M1", "C1"]
    assert saved[0]["result"]["state"] == "data"
