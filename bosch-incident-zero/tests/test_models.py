import json
from pathlib import Path
import jsonschema
import pytest

from src.models.incident import (
    IncidentReport,
    IncidentSeverity,
    IncidentStatus,
    EvidencePayload,
    RemediationPayload,
)
from src.faultctl.flagd_adapter import FlagdAdapter


def test_incident_report_validates_against_json_schema() -> None:
    schema_path = Path(__file__).resolve().parent.parent / "config" / "incident_schema.json"
    assert schema_path.exists(), f"Schema file not found at {schema_path}"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    report = IncidentReport(
        incident_id="INC-20261023-001",
        timestamp="2026-10-23T12:00:00Z",
        status=IncidentStatus.DIAGNOSED,
        target_service="cart",
        impacted_services=["frontend", "checkout"],
        severity=IncidentSeverity.HIGH,
        root_cause_summary="Cart service experiencing simulated failure via flag cartFailure.",
        confidence_score=0.95,
        evidence=EvidencePayload(
            trace_ids=["4bf92f3577b34da6a3ce929d0e0e4736"],
            metrics_summary={"error_rate_delta": 0.85, "baseline_error_rate": 0.01},
            log_excerpts=["CartService.GetCart: internal server error"],
        ),
        remediation=RemediationPayload(
            action_id="ACT-101",
            recommended_action="Revert flagd cartFailure flag to off",
            action_parameters={"flag": "cartFailure", "target_variant": "off"},
            requires_approval=True,
            approval_status="PENDING",
            dry_run=True,
        ),
    )

    data = report.to_schema_dict()
    # Validate against JSON schema draft 2020-12
    jsonschema.validate(instance=data, schema=schema)


def test_flagd_adapter(tmp_path: Path) -> None:
    config_file = tmp_path / "test.flagd.json"
    dummy_flags = {
        "flags": {
            "cartFailure": {
                "state": "ENABLED",
                "defaultVariant": "off",
                "variants": {
                    "off": 0,
                    "100%": 1,
                    "50%": 0.5
                }
            }
        }
    }
    config_file.write_text(json.dumps(dummy_flags), encoding="utf-8")

    adapter = FlagdAdapter(flagd_config_path=config_file)
    assert "cartFailure" in adapter.list_available_faults()

    # Inject
    adapter.inject_fault("cartFailure", variant="100%")
    state = adapter.get_fault_state("cartFailure")
    assert state["defaultVariant"] == "100%"

    # Revert
    adapter.revert_fault("cartFailure")
    state = adapter.get_fault_state("cartFailure")
    assert state["defaultVariant"] == "off"
