import json
from pathlib import Path

import pytest

from oncall.schema import IncidentRecord

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.mark.parametrize("name", ["diagnosis_payment", "diagnosis_low_confidence"])
def test_fixture_matches_schema_and_cites_real_evidence(name):
    record = IncidentRecord.model_validate(json.loads((FIXTURES / f"{name}.json").read_text()))
    known = {e.id for e in record.evidence}
    assert set(record.diagnosis.evidence_ids) <= known


def test_low_confidence_fixture_escalates():
    record = IncidentRecord.model_validate_json((FIXTURES / "diagnosis_low_confidence.json").read_text())
    assert record.diagnosis.escalate
