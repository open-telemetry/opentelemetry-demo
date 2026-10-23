from oncall.models import MAX_EVIDENCE_ITEMS, MAX_SUMMARY_CHARS, make_error, make_result


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
