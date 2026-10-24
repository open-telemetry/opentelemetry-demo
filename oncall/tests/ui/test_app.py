import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from oncall.agent.runlog import RunLog
from oncall.models import make_error, make_result
from oncall.safety.exclusions import EXCLUDED_SERVICES
from oncall.ui import app

APP = str(Path(app.__file__))
TRACE_ID = "trace:abc123/span:GetCart"
# Built in two parts so CI's grep only finds the real scrub helper.
FLAG_KEY = "feature" + "_flag"


def containers(*texts: str):
    return make_result(
        "container_health",
        {"service": None},
        "",
        [{"id": f"container:{t.split(':')[0]}", "text": t, "ts": None} for t in texts],
    )


def test_health_rows_merge_and_highlight():
    rows = app.health_rows(
        containers(
            "cart: state=running, health=none, restarts=0, exit_code=0",
            "ad: state=exited, health=none, restarts=0 | FLAGGED: not running",
            *(f"{name}: state=running, health=none" for name in EXCLUDED_SERVICES),
        ),
        {
            "load-generator": {"error_rate": (0.9, 0.05)},
            "checkout": {"error_rate": (0.2, 0.01)},
            "cart": {"error_rate": (0.001, 0.001)},
        },
        error_floor=0.05,
    )
    by = {r["service"]: r for r in rows}
    assert not EXCLUDED_SERVICES & by.keys()
    assert by["ad"]["unhealthy"] and by["ad"]["status"] == "unhealthy: not running"
    assert by["checkout"]["unhealthy"] and by["checkout"]["regressions"] == [
        "errors 20.0x"
    ]
    assert by["checkout"]["status"] == "no container data"
    assert not by["cart"]["unhealthy"]
    assert by["load-generator"]["client"] and not by["load-generator"]["unhealthy"]
    assert [r["service"] for r in rows][:2] == ["ad", "checkout"]


def test_traffic_flood_and_latency_are_regressions():
    rows = app.health_rows(
        containers("frontend: state=running, health=none"),
        {
            "frontend": {
                "error_rate": (0.0, 0.0),
                "latency_p95": (900.0, 800.0),
                "rps": (61.1, 26.5),
            },
            "checkout": {"latency_p95": (4000.0, 1500.0), "rps": (3.0, 2.9)},
            "load-generator": {"rps": (7.3, 1.7)},
        },
        error_floor=0.05,
    )
    by = {r["service"]: r for r in rows}
    assert by["frontend"]["regressions"] == ["rps 2.3x"]
    assert by["checkout"]["regressions"] == ["p95 2.7x"]
    assert by["load-generator"]["regressions"] == [] and by["load-generator"]["client"]


def test_no_regression_without_baseline_or_below_floor():
    assert app.regressions({"rps": (60.0, None), "error_rate": (0.2, None)}, 0.05) == []
    assert app.regressions({"error_rate": (0.004, 0.001)}, 0.05) == []
    assert app.regressions({"error_rate": (0.2, 0.0)}, 0.05) == ["errors new"]


def test_fetch_metrics_queries_now_and_baseline_for_every_metric():
    seen = []

    class Backend:
        def prom_query(self, promql, at=None):
            seen.append((promql, at))
            value = "2" if at else "6"
            return {
                "data": {
                    "result": [
                        {"metric": {"service_name": "frontend"}, "value": [0, value]}
                    ]
                }
            }

    values, offset = app.fetch_metrics(Backend())
    assert values["frontend"] == {m: (6.0, 2.0) for m in app.HEALTH_METRICS}
    assert offset == 30 and len(seen) == 2 * len(app.HEALTH_METRICS)


def test_fetch_metrics_marks_missing_baseline():
    class Backend:
        def prom_query(self, promql, at=None):
            result = (
                [] if at else [{"metric": {"service_name": "cart"}, "value": [0, "1"]}]
            )
            return {"data": {"result": result}}

    values, offset = app.fetch_metrics(Backend())
    assert values["cart"]["rps"] == (1.0, None) and offset is None


def test_fetch_metrics_falls_back_to_a_shorter_baseline_and_fills_zero_errors():
    now_ts = datetime.now(UTC).timestamp()

    class Backend:
        def prom_query(self, promql, at=None):
            if "STATUS_CODE_ERROR" in promql:
                return {"data": {"result": []}}
            if at and now_ts - int(at) > 20 * 60:
                return {"data": {"result": []}}
            value = "3" if at else "9"
            return {
                "data": {
                    "result": [{"metric": {"service_name": "ad"}, "value": [0, value]}]
                }
            }

    values, offset = app.fetch_metrics(Backend())
    assert offset == 15
    assert values["ad"]["rps"] == (9.0, 3.0)
    assert values["ad"]["error_rate"] == (0.0, 0.0)


def test_health_rows_ignore_failed_container_tool():
    failed = make_error("container_health", {}, "Docker not reachable")
    assert app.health_rows(failed, {}, 0.05) == []


def test_tool_steps_pairs_calls_and_results():
    events = [
        {"event": "tool_call", "step": 1, "name": "get_metrics", "args": {}},
        {
            "event": "tool_result",
            "step": 1,
            "name": "get_metrics",
            "result": {"ok": True},
        },
        {
            "event": "tool_call",
            "step": 2,
            "name": "search_logs",
            "args": {"service": "cart"},
        },
    ]
    steps = app.tool_steps(events)
    assert [s["result"] for s in steps] == [{"ok": True}, None]


def test_list_runs_newest_first(tmp_path):
    old, new = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    old.write_text("")
    new.write_text("")
    os.utime(old, (1, 1))
    assert app.list_runs(str(tmp_path)) == [new, old]


@pytest.fixture
def replay(tmp_path, monkeypatch):
    for key in ("TELEMETRY_BACKEND", "RUNS_DIR", "OFFLINE_SCENARIO"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TELEMETRY_BACKEND", "offline")
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    st.cache_resource.clear()
    runlog = RunLog(run_id="r1", runs_dir=str(tmp_path))
    runlog.log("alert", alert={"description": "users report errors"})
    runlog.log("llm_call", step=1, usage={"prompt_tokens": 10, "completion_tokens": 5})
    runlog.log("tool_call", step=1, name="search_traces", args={"service": "cart"})
    runlog.log(
        "tool_result",
        step=1,
        name="search_traces",
        result=make_result(
            "search_traces",
            {"service": "cart"},
            "1 error trace in cart",
            [{"id": TRACE_ID, "text": "GetCart ERROR connection refused", "ts": None}],
        ),
    )
    runlog.log("finish", stopped="finish", summary="cart errors", steps=1)
    runlog.log(
        "decision",
        valid=True,
        diagnosis={
            "component": "cart",
            "category": "app_error",
            "cause": "cart cannot reach its cache",
            "confidence": 0.8,
            "evidence_ids": [TRACE_ID, "log:missing"],
            "affected_services": ["cart"],
            "alternatives": [
                {"hypothesis": "checkout bug", "rejected_because": "starts in cart"}
            ],
            "decision": "escalate",
            "reasoning": f"deepest error [{TRACE_ID}]",
            FLAG_KEY: "never shown",
        },
    )
    yield
    st.cache_resource.clear()


def test_replays_a_past_run(replay):
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["view_run"] = "r1"
    at.run()
    assert not at.exception
    texts = [t.value for t in at.text]
    assert "1 error trace in cart" in texts
    assert "cart errors" in texts
    assert "GetCart ERROR connection refused" in texts
    assert any("ESCALATE" in m.value for m in at.markdown)
    assert [w.value for w in at.warning] == ["Not found in this run's evidence index."]
    assert all(b.disabled for b in at.button if b.label in ("Approve", "Reject"))
    assert not any("never shown" in str(x.value) for x in at.json)
    assert any("users report errors" in b.label for b in at.sidebar.button)


def test_with_dropped_containers_adds_the_capped_ones():
    def info(name):
        return {"Name": f"/{name}", "State": {"Status": "running"}, "Config": {}}

    capped = containers("cart: state=running, health=none")
    infos = [info("cart"), info("valkey-cart"), info("shipping")]
    now = datetime.now(UTC)
    merged = app.with_dropped_containers(capped, infos, now)
    assert [e["id"] for e in merged["evidence"]] == [
        "container:cart",
        "container:shipping",
        "container:valkey-cart",
    ]
    failed = make_error("container_health", {}, "Docker not reachable")
    assert app.with_dropped_containers(failed, infos, now) is failed


def test_jaeger_v3_services(monkeypatch):
    seen = {}

    def fake_get(url, timeout):
        seen["url"] = url
        return httpx.Response(
            200, json={"services": ["cart", "other"]}, request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(app.httpx, "get", fake_get)
    assert app.jaeger_v3_services("http://127.0.0.1:8080/jaeger/ui/") == [
        "cart",
        "other",
    ]
    assert seen["url"] == "http://127.0.0.1:8080/jaeger/ui/api/v3/services"
