"""Incident memory: similarity ranking, hint-only output, never reads eval answers or flag data."""
from __future__ import annotations

import json

from src.memory import IncidentMemory, format_hints
from src.memory import incident_memory as im


def write_transcript(root, incident_id, alert, service, category, summary, confidence="high", escalate=False,
                     extra=None):
    d = root / incident_id
    d.mkdir(parents=True)
    t = {"incident_id": incident_id, "alert": alert,
         "diagnosis": {"root_cause": {"service": service, "category": category, "summary": summary}},
         "gate": {"final_confidence": confidence, "escalate": escalate}}
    t.update(extra or {})
    (d / "transcript.json").write_text(json.dumps(t))
    return d


def test_finds_the_most_similar_incident(tmp_path):
    write_transcript(tmp_path, "INC-PAY", "Error rate above 5% on checkout", "payment", "dependency_unreachable",
                     "checkout calls to payment never reach payment")
    write_transcript(tmp_path, "INC-AD", "High latency on ad", "ad", "latency_without_errors", "ad is slow")
    hints = IncidentMemory.from_dir(tmp_path).find_similar("Checkout error rate spiking", "payment unreachable")
    assert hints[0]["incident_id"] == "INC-PAY"
    assert hints[0]["diagnosed_as"] == "payment/dependency_unreachable"
    assert "checkout" in hints[0]["matched_services"] and hints[0]["hint_only"] is True
    assert all(h["incident_id"] != "INC-AD" for h in hints)


def test_no_overlap_returns_nothing(tmp_path):
    write_transcript(tmp_path, "INC-AD", "High latency on ad", "ad", "latency_without_errors", "ad is slow")
    assert IncidentMemory.from_dir(tmp_path).find_similar("Kafka queue lag on accounting") == []


def test_exclude_current_incident_and_limit(tmp_path):
    for i in range(5):
        write_transcript(tmp_path, f"INC-{i}", "checkout errors", "payment", "errors_on_operation", "payment fails")
    hints = IncidentMemory.from_dir(tmp_path).find_similar("checkout errors", limit=2, exclude="INC-0")
    assert [h["incident_id"] for h in hints] == ["INC-1", "INC-2"]


def test_never_reads_eval_answers(tmp_path, monkeypatch):
    run = tmp_path / "eval-20261024-050000"
    write_transcript(run, "p1-S", "checkout errors", "payment", "errors_on_operation", "payment fails")
    (run / "results.json").write_text(json.dumps([{"expected": {"service": "SECRET-ANSWER"}}]))
    (run / "summary.json").write_text("{}")
    (run / "results.jsonl").write_text("{}\n")
    opened = []
    real_read = im.Path.read_text

    def spy(self, *a, **kw):
        opened.append(self.name)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(im.Path, "read_text", spy)
    mem = IncidentMemory.from_dir(tmp_path)
    assert [p.incident_id for p in mem.incidents] == ["p1-S"]
    assert opened == ["transcript.json"]
    assert "SECRET-ANSWER" not in json.dumps(mem.find_similar("checkout errors"))


def test_flag_data_is_stripped(tmp_path):
    write_transcript(tmp_path, "INC-F", "checkout errors", "payment", "errors_on_operation", "payment fails",
                     extra={"alert": "checkout errors",
                            "diagnosis": {"root_cause": {"service": "payment", "category": "errors_on_operation",
                                                         "summary": "payment fails"},
                                          "attributes": [{"key": "feature_flag.key", "value": "paymentFailure"}]}})
    mem = IncidentMemory.from_dir(tmp_path)
    assert "paymentfailure" not in mem.incidents[0].keywords
    assert "paymentFailure" not in json.dumps(mem.find_similar("checkout errors"))


def test_report_only_folder_and_broken_files(tmp_path):
    d = tmp_path / "OLD-1"
    d.mkdir()
    (d / "report.json").write_text(json.dumps({"incident_id": "OLD-1", "target_service": "cart",
                                               "root_cause_summary": "cart redis connection refused"}))
    bad = tmp_path / "BROKEN"
    bad.mkdir()
    (bad / "transcript.json").write_text("{not json")
    mem = IncidentMemory.from_dir(tmp_path)
    assert [p.incident_id for p in mem.incidents] == ["OLD-1"]
    assert mem.find_similar("cart errors")[0]["diagnosed_as"] == "cart/?"


def test_missing_dir_is_empty(tmp_path):
    assert IncidentMemory.from_dir(tmp_path / "nope").incidents == []


def test_format_hints_says_hint_only():
    text = format_hints([{"incident_id": "INC-1", "diagnosed_as": "payment/dependency_unreachable",
                          "confidence": "high", "escalated": False, "matched_services": ["checkout"],
                          "matched_keywords": ["errors"]}])
    assert "hint only" in text and "not evidence" in text and "INC-1" in text
    assert format_hints([]) == "Similar past incidents: none found."
