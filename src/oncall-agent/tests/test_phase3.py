from pathlib import Path
import shutil

import pytest

from app.detector import Alert, Symptom, detector
from app.evidence import EvidenceLedger
from app.validator import validate_diagnosis


@pytest.fixture
def temp_ledger(tmp_path: Path) -> EvidenceLedger:
    return EvidenceLedger(incident_id="INC-UNIT-TEST", storage_dir=tmp_path)


def test_fabricated_citation_rejected_by_validator(temp_ledger: EvidenceLedger) -> None:
    # 1. Record authentic tool output in ledger
    raw_metric_output = (
        "| Service | Req/s | Error % | p95 (ms) | Baseline (ms) | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| payment | 0.25 | 100.0% | 450.0 | 12.0 | CRITICAL |"
    )
    eid1 = temp_ledger.record_evidence(
        tool_name="get_health_overview",
        tool_args={"lookback_min": 15},
        raw_result=raw_metric_output,
        ev_type="metric",
    )
    assert eid1 == "E1"

    raw_log_output = (
        "Logs for payment (lookback 15m, 10 total hits):\n"
        "[19:50:12] [ERROR] Failed to connect to payment gateway [trace: a1b2c3d4e5f67890123456789abcdef0]"
    )
    eid2 = temp_ledger.record_evidence(
        tool_name="search_logs",
        tool_args={"service": "payment"},
        raw_result=raw_log_output,
        ev_type="log",
    )
    assert eid2 == "E2"

    # 2. Test valid citation
    valid_diag = {
        "component": "payment",
        "cause_category": "service_fault_injected_errors",
        "cause_description": "Payment service experiencing 100% error rate connecting to gateway",
        "confidence": 0.90,
        "evidence": [
            {
                "evidence_id": "E1",
                "type": "metric",
                "ref": "payment error_pct 100.0%",
                "why_it_matters": "Shows 100% charge request failure",
            },
            {
                "evidence_id": "E2",
                "type": "log",
                "ref": "Failed to connect to payment gateway",
                "why_it_matters": "Exact log exception message",
            },
        ],
        "alternatives_considered": ["dependency_unavailable"],
        "recommended_runbook_ids": ["RB-PAYMENT-FLAG"],
    }
    res_valid = validate_diagnosis(temp_ledger, valid_diag)
    assert res_valid.is_valid is True
    assert len(res_valid.invented_evidence) == 0
    assert len(res_valid.valid_evidence) == 2
    assert res_valid.calibrated_confidence > 0.70

    # 3. Test fabricated citation with non-existent ref
    fabricated_ref_diag = {
        "component": "payment",
        "cause_category": "service_fault_injected_errors",
        "cause_description": "Payment service failing",
        "confidence": 0.95,
        "evidence": [
            {
                "evidence_id": "E1",
                "type": "metric",
                "ref": "completely_invented_metric_value_9999",
                "why_it_matters": "Fake citation",
            }
        ],
        "alternatives_considered": ["none"],
    }
    res_fab = validate_diagnosis(temp_ledger, fabricated_ref_diag)
    assert res_fab.is_valid is False
    assert len(res_fab.invented_evidence) == 1
    assert "invented evidence" in res_fab.invented_evidence[0]["reason"]
    assert res_fab.escalate_required is True

    # 4. Test non-existent evidence ID
    non_existent_eid_diag = {
        "component": "payment",
        "cause_category": "service_fault_injected_errors",
        "cause_description": "Payment service failing",
        "confidence": 0.90,
        "evidence": [
            {
                "evidence_id": "E99",
                "type": "metric",
                "ref": "any ref",
                "why_it_matters": "Fake ID",
            }
        ],
    }
    res_eid = validate_diagnosis(temp_ledger, non_existent_eid_diag)
    assert res_eid.is_valid is False
    assert len(res_eid.invented_evidence) == 1
    assert "does not exist in ledger" in res_eid.invented_evidence[0]["reason"]


def test_calibrated_confidence_penalties(temp_ledger: EvidenceLedger) -> None:
    temp_ledger.record_evidence(
        tool_name="get_health_overview",
        tool_args={},
        raw_result="payment 100.0% error",
        ev_type="metric",
    )

    # Missing alternatives incurs penalty
    diag_no_alts = {
        "component": "payment",
        "cause_category": "service_fault_injected_errors",
        "cause_description": "payment error",
        "confidence": 0.95,
        "evidence": [{"evidence_id": "E1", "type": "metric", "ref": "payment 100.0%", "why_it_matters": "test"}],
        "alternatives_considered": [],
    }
    res = validate_diagnosis(temp_ledger, diag_no_alts)
    assert res.evidence_score <= 0.65
    assert res.calibrated_confidence < res.model_confidence

    # Unknown category caps confidence at 0.40 and forces escalation
    diag_unknown = {
        "component": "payment",
        "cause_category": "unknown",
        "cause_description": "unknown error",
        "confidence": 0.85,
        "evidence": [{"evidence_id": "E1", "type": "metric", "ref": "payment 100.0%", "why_it_matters": "test"}],
        "alternatives_considered": ["alt1"],
    }
    res_unk = validate_diagnosis(temp_ledger, diag_unknown)
    assert res_unk.calibrated_confidence <= 0.40
    assert res_unk.escalate_required is True


def test_detector_alert_symptoms_only() -> None:
    # Verify that Symptom and Alert data structures convey symptoms only, never a cause
    symptom = Symptom(
        type="error_ratio",
        service="payment",
        metric="error_percentage",
        value=100.0,
        threshold=5.0,
        description="Service 'payment' error ratio is 100.0%",
    )
    alert = Alert(
        incident_id="INC-TEST-SYMPTOMS",
        timestamp="2026-10-24T00:00:00Z",
        fingerprint="payment:error_ratio",
        symptoms=[symptom],
    )
    alert_json = alert.model_dump_json()
    assert "cause" not in alert_json.lower()
    assert "flag" not in alert_json.lower()
    assert alert.symptoms[0].service == "payment"
    assert alert.symptoms[0].value == 100.0
