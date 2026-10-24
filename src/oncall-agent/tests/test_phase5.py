from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.approval import ApprovalStore, IncidentRecord, IncidentState, approval_store
from app.main import app
from app.memory import (
    init_memory_db,
    save_to_memory,
    search_memory,
    find_memory_assist,
    reindex_from_reports,
)
from app.prevention import generate_prevention, validate_promql, write_prevention_markdown
from app.reporter import build_report, validate_report_json, write_report


def test_memory_save_and_exact_fingerprint_retrieval(tmp_path: Path):
    db_file = tmp_path / "memory.sqlite"
    init_memory_db(db_file)

    rec1 = IncidentRecord(
        incident_id="INC-HIST-001",
        state=IncidentState.RESOLVED,
        detected_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        fingerprint="payment:error_ratio",
        symptoms=[{"type": "error_ratio", "service": "payment", "value": 100.0}],
        diagnosis={
            "component": "payment",
            "cause_category": "service_fault_injected_errors",
            "cause_description": "paymentFailure flag set to 100%",
        },
        execution_results=[{"action": "set_feature_flag", "runbook_id": "RB-001"}],
    )
    save_to_memory(rec1, steps_used=6, db_path=db_file)

    # Search with matching fingerprint and symptom query
    matches = search_memory("payment 100% error rate failure", fingerprint="payment:error_ratio", db_path=db_file)
    assert len(matches) == 1
    assert matches[0]["incident_id"] == "INC-HIST-001"
    assert matches[0]["outcome"] == "fixed"
    assert matches[0]["similarity"] >= 0.85


def test_memory_failed_outcome_deprioritization(tmp_path: Path):
    db_file = tmp_path / "memory.sqlite"
    init_memory_db(db_file)

    # Incident with failed outcome (rolled back)
    rec_failed = IncidentRecord(
        incident_id="INC-FAIL-001",
        state=IncidentState.ROLLED_BACK,
        detected_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        fingerprint="cart:error_ratio",
        symptoms=[{"type": "error_ratio", "service": "cart", "value": 50.0}],
        diagnosis={"component": "cart", "cause_category": "service_fault_injected_errors"},
        execution_results=[{"action": "restart_service"}],
    )
    save_to_memory(rec_failed, steps_used=8, db_path=db_file)

    # Incident with successful outcome (resolved)
    rec_fixed = IncidentRecord(
        incident_id="INC-FIXED-001",
        state=IncidentState.RESOLVED,
        detected_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        fingerprint="cart:error_ratio",
        symptoms=[{"type": "error_ratio", "service": "cart", "value": 50.0}],
        diagnosis={"component": "cart", "cause_category": "service_fault_injected_errors"},
        execution_results=[{"action": "set_feature_flag", "runbook_id": "RB-002"}],
    )
    save_to_memory(rec_fixed, steps_used=4, db_path=db_file)

    matches = search_memory("cart error ratio 50%", fingerprint="cart:error_ratio", db_path=db_file)
    assert len(matches) == 2
    # The fixed incident must be ranked above the failed incident
    assert matches[0]["incident_id"] == "INC-FIXED-001"
    assert matches[0]["outcome"] == "fixed"
    assert matches[1]["incident_id"] == "INC-FAIL-001"
    assert matches[1]["outcome"] == "not_fixed"


def test_memory_assist_calculation(tmp_path: Path):
    db_file = tmp_path / "memory.sqlite"
    init_memory_db(db_file)

    rec = IncidentRecord(
        incident_id="INC-BASE-100",
        state=IncidentState.RESOLVED,
        detected_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        fingerprint="payment:error_ratio",
        symptoms=[{"type": "error_ratio", "service": "payment", "value": 100.0}],
        diagnosis={"component": "payment", "cause_category": "service_fault_injected_errors"},
        execution_results=[{"runbook_id": "RB-001", "action": "set_feature_flag"}],
    )
    save_to_memory(rec, steps_used=8, db_path=db_file)

    assist = find_memory_assist(
        fingerprint="payment:error_ratio",
        symptom_summary="payment 100% error ratio",
        current_steps=3,
        db_path=db_file,
    )
    assert assist is not None
    assert assist["matched_incident"] == "INC-BASE-100"
    assert assist["prev_steps"] == 8
    assert assist["current_steps"] == 3
    assert assist["steps_saved"] == 5
    assert assist["recommended_runbook"] == "RB-001"


def test_reindex_from_reports(tmp_path: Path):
    db_file = tmp_path / "memory.sqlite"
    rep_dir = tmp_path / "reports"
    rep_dir.mkdir(parents=True)

    report_sample = {
        "schema_version": "1.0",
        "incident_id": "INC-REINDEX-01",
        "status": "resolved",
        "detected_at": "2026-10-24T00:00:00Z",
        "resolved_at": "2026-10-24T00:05:00Z",
        "timeline": [{"ts": "2026-10-24T00:01:00Z", "event": "DETECTED"}],
        "symptoms": [{"service": "payment", "type": "error_ratio"}],
        "root_cause": {
            "component": "payment",
            "category": "service_fault_injected_errors",
            "description": "payment failure",
        },
        "actions": [{"runbook_id": "RB-001", "action": "set_feature_flag"}],
    }
    (rep_dir / "INC-REINDEX-01.json").write_text(json.dumps(report_sample))

    count = reindex_from_reports(reports_dir=rep_dir, db_path=db_file)
    assert count == 1

    matches = search_memory("payment", fingerprint="payment:service_fault_injected_errors", db_path=db_file)
    assert len(matches) == 1
    assert matches[0]["incident_id"] == "INC-REINDEX-01"


def test_prevention_generation_and_promql_validation(tmp_path: Path):
    rec = IncidentRecord(
        incident_id="INC-PREV-01",
        state=IncidentState.RESOLVED,
        detected_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        fingerprint="payment:error_ratio",
        diagnosis={
            "component": "payment",
            "cause_category": "service_fault_injected_errors",
            "cause_description": "Payment gateway charge failures",
        },
    )

    suggestions = generate_prevention(rec)
    assert len(suggestions) == 3

    types = [s["type"] for s in suggestions]
    assert "alerting" in types
    assert "config" in types
    assert "code" in types

    alerting_item = next(s for s in suggestions if s["type"] == "alerting")
    assert "payment" in alerting_item["change"].lower()
    assert "groups:" in alerting_item["change"]

    # Write prevention markdown
    import app.prevention
    orig_dir = app.prevention.PREVENTION_DIR
    try:
        app.prevention.PREVENTION_DIR = tmp_path / "prevention"
        md_path = write_prevention_markdown("INC-PREV-01", suggestions)
        assert md_path.exists()
        content = md_path.read_text()
        assert "INC-PREV-01" in content
        assert "ALERTING" in content
    finally:
        app.prevention.PREVENTION_DIR = orig_dir


def test_report_includes_prevention_and_memory_assist(tmp_path: Path):
    rec = IncidentRecord(
        incident_id="INC-FULL-P5",
        state=IncidentState.RESOLVED,
        detected_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        fingerprint="payment:error_ratio",
        diagnosis={"component": "payment", "cause_category": "service_fault_injected_errors"},
        memory_assist={
            "matched_incident": "INC-BASE-100",
            "similarity": 0.90,
            "prev_steps": 7,
            "current_steps": 3,
            "steps_saved": 4,
        },
    )

    report = build_report(rec)
    assert report.memory_assist is not None
    assert report.memory_assist["matched_incident"] == "INC-BASE-100"
    assert len(report.prevention) >= 1

    # Validate against JSON schema
    report_dict = json.loads(report.model_dump_json())
    validate_report_json(report_dict)


def test_fastapi_phase5_endpoints(tmp_path: Path):
    client = TestClient(app)

    # Reindex endpoint
    res_reindex = client.post("/memory/reindex")
    assert res_reindex.status_code == 200
    assert "reindexed" in res_reindex.json()["status"]

    # Get memory endpoint
    res_mem = client.get("/memory")
    assert res_mem.status_code == 200
    assert isinstance(res_mem.json(), list)

    # Prevention endpoint on existing incident
    test_id = "INC-TEST-PREV"
    rec = approval_store.create(incident_id=test_id, fingerprint="payment:p5", symptoms=[])
    rec.diagnosis = {"component": "payment", "cause_category": "service_fault_injected_errors"}
    approval_store.transition(rec, IncidentState.RESOLVED, "Resolved")

    res_prev = client.get(f"/incidents/{test_id}/prevention")
    assert res_prev.status_code == 200
    assert len(res_prev.json()["prevention"]) == 3
