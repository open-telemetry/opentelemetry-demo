from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.approval import ApprovalStore, IncidentRecord, IncidentState, approval_store
from app.proposer import Proposer, Proposal
from app.reporter import build_report, validate_report_json, write_report
from app.runbook import find_matching_runbooks, resolve_params
from app.main import app


def test_runbook_matching_and_least_invasive_priority():
    # Service fault injected errors on payment
    matched = find_matching_runbooks("service_fault_injected_errors", "payment")
    assert len(matched) >= 1
    # First action should be flag disable (least invasive), NOT restart
    assert matched[0].action == "set_feature_flag"
    assert "payment" in matched[0].id.lower() or "payment" in matched[0].description.lower()

    # Container down on payment
    matched_container = find_matching_runbooks("container_down_or_crashloop", "payment")
    assert len(matched_container) >= 1
    assert matched_container[0].action == "restart_service"


def test_runbook_resolve_params():
    entry_flag = find_matching_runbooks("service_fault_injected_errors", "payment")[0]
    diag = {
        "component": "payment",
        "cause_category": "service_fault_injected_errors",
        "cause_description": "paymentFailure flag is causing 100% errors",
    }
    params = resolve_params(entry_flag, diag)
    assert params.get("target") == "payment" or params.get("flag") or params.get("service")


def test_hmac_approval_token_validity_and_tamper_detection(tmp_path: Path):
    store = ApprovalStore(storage_dir=tmp_path)
    inc_id = "INC-TEST-HMAC"
    action = "set_feature_flag"
    params = {"name": "paymentFailure", "state": "off"}

    # Mint valid token
    token = store.mint_approval_token(inc_id, action, params, ttl_s=60)
    valid, reason = store.verify_approval_token(token, inc_id, action, params)
    assert valid is True
    assert reason == "ok"

    # Action mismatch
    valid, reason = store.verify_approval_token(token, inc_id, "restart_service", params)
    assert valid is False
    assert "action mismatch" in reason.lower()

    # Params mismatch (tampered payload)
    valid, reason = store.verify_approval_token(token, inc_id, action, {"name": "otherFlag", "state": "off"})
    assert valid is False
    assert "params mismatch" in reason.lower()

    # Incident ID mismatch
    valid, reason = store.verify_approval_token(token, "INC-OTHER", action, params)
    assert valid is False
    assert "incident_id mismatch" in reason.lower()

    # Expired token
    expired_token = store.mint_approval_token(inc_id, action, params, ttl_s=-10)
    valid, reason = store.verify_approval_token(expired_token, inc_id, action, params)
    assert valid is False
    assert "expired" in reason.lower()


def test_incident_state_transitions(tmp_path: Path):
    store = ApprovalStore(storage_dir=tmp_path)
    rec = store.create(
        incident_id="INC-STATE-FLOW",
        fingerprint="payment:error_ratio",
        symptoms=[{"type": "error_ratio", "service": "payment", "value": 100.0}],
    )
    assert rec.state == IncidentState.DETECTED

    store.transition(rec, IncidentState.INVESTIGATING, "Investigation started")
    assert store.get("INC-STATE-FLOW").state == IncidentState.INVESTIGATING

    store.transition(rec, IncidentState.DIAGNOSED, "Diagnosis reached")
    assert store.get("INC-STATE-FLOW").state == IncidentState.DIAGNOSED

    store.transition(rec, IncidentState.AWAITING_APPROVAL, "Waiting for human approval")
    assert store.get("INC-STATE-FLOW").state == IncidentState.AWAITING_APPROVAL


def test_report_generation_and_schema_validation(tmp_path: Path):
    # Setup record
    rec = IncidentRecord(
        incident_id="INC-SCHEMA-TEST",
        state=IncidentState.RESOLVED,
        detected_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        fingerprint="payment:error_ratio",
        symptoms=[{"type": "error_ratio", "service": "payment", "value": 100.0, "threshold": 5.0}],
        diagnosis={
            "component": "payment",
            "cause_category": "service_fault_injected_errors",
            "cause_description": "Payment failure flag enabled",
            "confidence": 0.95,
            "evidence": [
                {
                    "evidence_id": "E1",
                    "type": "metric",
                    "ref": "payment 100.0%",
                    "why_it_matters": "Shows 100% error rate",
                }
            ],
            "alternatives_considered": ["dependency_unavailable"],
        },
        validation={
            "model_confidence": 0.95,
            "evidence_score": 0.85,
            "calibrated_confidence": 0.85,
        },
        execution_results=[
            {
                "action": "set_feature_flag",
                "params": {"name": "paymentFailure", "state": "off"},
                "result": {"status": "ok"},
            }
        ],
        verification={"passed": True, "checks": {"error_ratio": "< 2%"}},
    )

    report = build_report(rec)
    report_dict = json.loads(report.model_dump_json())

    # Validate against JSON schema
    validate_report_json(report_dict)

    # Test writing to disk
    import app.reporter
    orig_dir = app.reporter.REPORTS_DIR
    try:
        app.reporter.REPORTS_DIR = tmp_path / "reports"
        json_path, md_path = write_report(rec)
        assert json_path.exists()
        assert md_path.exists()
        # Verify markdown content
        md_text = md_path.read_text()
        assert "INC-SCHEMA-TEST" in md_text
        assert "RESOLVED" in md_text
        assert "payment" in md_text
    finally:
        app.reporter.REPORTS_DIR = orig_dir


def test_fastapi_endpoints():
    client = TestClient(app)

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # 2. Kill switch toggle
    res_ks = client.post("/killswitch", json={"engaged": True})
    assert res_ks.status_code == 200
    assert res_ks.json()["engaged"] is True

    res_ks_get = client.get("/killswitch")
    assert res_ks_get.status_code == 200
    assert res_ks_get.json()["engaged"] is True

    # Reset kill switch
    client.post("/killswitch", json={"engaged": False})

    # 3. Create mock incident in store for approval testing
    test_id = "INC-API-TEST"
    rec = approval_store.create(
        incident_id=test_id,
        fingerprint="cart:error_ratio",
        symptoms=[{"type": "error_ratio", "service": "cart", "value": 50.0}],
    )
    rec.proposals = [
        {
            "runbook_id": "RB-002",
            "action": "set_feature_flag",
            "params": {"name": "cartFailure", "state": "off"},
            "reason": "Disable failing cart flag",
            "expected_recovery_signal": "cart error ratio drops below 2%",
            "rollback_plan": "rollback",
        }
    ]
    rec.diagnosis = {
        "component": "cart",
        "cause_category": "service_fault_injected_errors",
        "cause_description": "cart failure",
    }
    approval_store.transition(rec, IncidentState.AWAITING_APPROVAL, "Ready for test")

    # 4. Fetch incident
    res_get = client.get(f"/incidents/{test_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["incident_id"] == test_id
    assert data["state"] == "AWAITING_APPROVAL"

    # 5. Dry run
    res_dry = client.post(f"/incidents/{test_id}/dry-run")
    assert res_dry.status_code == 200
    assert "dry_run_result" in res_dry.json()

    # 6. Reject flow on a second incident
    rej_id = "INC-REJECT-TEST"
    rec_rej = approval_store.create(
        incident_id=rej_id,
        fingerprint="cart:reject",
        symptoms=[],
    )
    approval_store.transition(rec_rej, IncidentState.AWAITING_APPROVAL, "Ready for rejection")
    res_rej = client.post(f"/incidents/{rej_id}/reject", json={"reason": "False positive"})
    assert res_rej.status_code == 200
    assert approval_store.get(rej_id).state == IncidentState.REJECTED
