"""Tests for RunLog event recording, retrieval, evidence indexing, and token usage."""

from pathlib import Path

from oncall.agent.runlog import RunLog


def test_init_creates_path_and_dir(tmp_path: Path):
    runs_dir = tmp_path / "custom_runs"
    rl = RunLog(run_id="test_run_123", runs_dir=str(runs_dir))

    assert rl.run_id == "test_run_123"
    assert rl.path == runs_dir / "test_run_123.jsonl"
    assert runs_dir.exists()


def test_default_init_generates_id(tmp_path: Path):
    rl = RunLog(runs_dir=str(tmp_path))
    assert rl.run_id is not None
    assert len(rl.run_id) > 5
    assert rl.path.name.endswith(".jsonl")


def test_log_and_events_round_trip(tmp_path: Path):
    rl = RunLog(run_id="roundtrip_run", runs_dir=str(tmp_path))

    rl.log("alert", signal="error_rate", service="checkoutservice", value=0.08)
    rl.log("tool_call", tool="get_metrics", service="checkoutservice")
    rl.log("decision", hypothesis="checkout service database slow", confidence=0.85)

    all_events = rl.events()
    assert len(all_events) == 3

    assert all_events[0]["event"] == "alert"
    assert all_events[0]["service"] == "checkoutservice"
    assert "ts" in all_events[0]

    assert all_events[1]["event"] == "tool_call"
    assert all_events[1]["tool"] == "get_metrics"

    assert all_events[2]["event"] == "decision"
    assert all_events[2]["confidence"] == 0.85


def test_events_filtering(tmp_path: Path):
    rl = RunLog(run_id="filter_run", runs_dir=str(tmp_path))

    rl.log("alert", alert_id="alt-1")
    rl.log("tool_call", tool="search_traces")
    rl.log("alert", alert_id="alt-2")
    rl.log("finish", status="success")

    alerts = rl.events(event="alert")
    assert len(alerts) == 2
    assert [a["alert_id"] for a in alerts] == ["alt-1", "alt-2"]

    finishes = rl.events(event="finish")
    assert len(finishes) == 1
    assert finishes[0]["status"] == "success"

    unknown = rl.events(event="nonexistent")
    assert unknown == []


def test_evidence_index_finds_ids_from_multiple_results(tmp_path: Path):
    rl = RunLog(run_id="evidence_run", runs_dir=str(tmp_path))

    # Tool result 1: direct evidence list
    rl.log(
        "tool_result",
        tool="get_metrics",
        ok=True,
        summary="High error rate on paymentservice",
        evidence=[
            {
                "id": "metric:rate(http_requests_total[5m])@2026-10-23T15:00:00Z",
                "text": "error_rate = 0.25 (threshold 0.05)",
                "ts": "2026-10-23T15:00:00Z",
            },
            {
                "id": "metric:latency_p95@2026-10-23T15:00:00Z",
                "text": "p95 latency = 2100ms",
                "ts": "2026-10-23T15:00:00Z",
            },
        ],
    )

    # Intermediate decision
    rl.log("decision", note="Checking traces for payment failure")

    # Tool result 2: nested under result dict, also using 'ref' field support
    rl.log(
        "tool_result",
        tool="search_traces",
        ok=True,
        result={
            "summary": "Payment RPC error span",
            "evidence": [
                {
                    "id": "trace:4bf92f3577b34da6a3ce929d0e0e4736/span:charge",
                    "text": "status code 500: insufficient funds",
                    "ts": "2026-10-23T15:01:12Z",
                },
                {
                    "ref": "log:paymentservice@2026-10-23T15:01:12Z",
                    "text": "ChargeFailedException: card declined",
                    "ts": "2026-10-23T15:01:12Z",
                },
            ],
        },
    )

    index = rl.evidence_index()
    assert len(index) == 4

    assert "metric:rate(http_requests_total[5m])@2026-10-23T15:00:00Z" in index
    assert "metric:latency_p95@2026-10-23T15:00:00Z" in index
    assert "trace:4bf92f3577b34da6a3ce929d0e0e4736/span:charge" in index
    assert "log:paymentservice@2026-10-23T15:01:12Z" in index

    ev1 = index["metric:rate(http_requests_total[5m])@2026-10-23T15:00:00Z"]
    assert "error_rate = 0.25" in ev1["text"]


def test_token_usage_aggregation(tmp_path: Path):
    rl = RunLog(run_id="token_run", runs_dir=str(tmp_path))

    # LLM call 1: direct token keys
    rl.log("llm_call", prompt_tokens=150, completion_tokens=50, total_tokens=200)

    # LLM call 2: nested usage dict
    rl.log(
        "llm_call",
        usage={
            "prompt_tokens": 300,
            "completion_tokens": 100,
            "total_tokens": 400,
        },
    )

    # Other event that shouldn't affect tokens
    rl.log("tool_call", tool="get_metrics")

    usage = rl.token_usage()
    assert usage["calls"] == 2
    assert usage["prompt_tokens"] == 450
    assert usage["completion_tokens"] == 150
    assert usage["total_tokens"] == 600


def test_concurrent_file_append_and_corruption_resilience(tmp_path: Path):
    rl = RunLog(run_id="append_run", runs_dir=str(tmp_path))
    rl.log("alert", count=1)
    rl.log("decision", count=2)

    # Simulate blank lines or invalid line in the file
    with open(rl.path, "a", encoding="utf-8") as f:
        f.write("\n\nINVALID_JSON_CORRUPTED_LINE\n\n")

    # Continue appending
    rl.log("action", count=3)

    events = rl.events()
    assert len(events) == 3
    assert [e["event"] for e in events] == ["alert", "decision", "action"]
