from typing import Any

from pydantic import BaseModel

from app.evidence import EvidenceLedger

CONFIDENCE_THRESHOLD = 0.70


class ValidationResult(BaseModel):
    is_valid: bool
    valid_evidence: list[dict[str, Any]]
    invented_evidence: list[dict[str, Any]]
    model_confidence: float
    evidence_score: float
    calibrated_confidence: float
    escalate_required: bool
    reason: str


def validate_diagnosis(
    ledger: EvidenceLedger,
    diagnosis: dict[str, Any],
    threshold: float = CONFIDENCE_THRESHOLD,
) -> ValidationResult:
    raw_citations = diagnosis.get("evidence", [])
    model_conf = float(diagnosis.get("confidence", 0.0))
    category = diagnosis.get("cause_category", "unknown")
    alternatives = diagnosis.get("alternatives_considered", [])

    if not isinstance(raw_citations, list) or len(raw_citations) == 0:
        return ValidationResult(
            is_valid=False,
            valid_evidence=[],
            invented_evidence=[],
            model_confidence=model_conf,
            evidence_score=0.0,
            calibrated_confidence=0.0,
            escalate_required=True,
            reason="Diagnosis provides no evidence citations",
        )

    valid_items: list[dict[str, Any]] = []
    invented_items: list[dict[str, Any]] = []

    for item in raw_citations:
        eid = str(item.get("evidence_id", ""))
        ref = str(item.get("ref", ""))
        ok, msg = ledger.verify_citation(eid, ref)
        if ok:
            valid_items.append(item)
        else:
            invented_items.append({"citation": item, "reason": msg})

    total_citations = len(raw_citations)
    valid_ratio = len(valid_items) / total_citations if total_citations > 0 else 0.0

    # Evidence diversity score
    ev_types = {str(item.get("type", "")) for item in valid_items if item.get("type")}
    diversity_factor = 0.50
    if len(ev_types) >= 3:
        diversity_factor = 1.00
    elif len(ev_types) == 2:
        diversity_factor = 0.85
    elif len(ev_types) == 1:
        diversity_factor = 0.65

    # Penalty if no competing alternatives were evaluated
    alt_penalty = 0.15 if not alternatives or len(alternatives) == 0 else 0.0

    # Composite evidence score
    evidence_score = round(max(0.0, min(1.0, (valid_ratio * diversity_factor) - alt_penalty)), 2)

    # Category unknown cap
    if category == "unknown":
        evidence_score = min(evidence_score, 0.40)

    # Calibrated confidence is min(model_confidence, evidence_score)
    calibrated_conf = round(min(model_conf, evidence_score), 2)

    escalate = False
    reasons: list[str] = []

    if invented_items:
        reasons.append(f"{len(invented_items)} of {total_citations} citations rejected as invented evidence")
    if calibrated_conf < threshold:
        escalate = True
        reasons.append(f"Calibrated confidence {calibrated_conf:.2f} is below threshold {threshold:.2f}")
    if category == "unknown":
        escalate = True
        reasons.append("Category is 'unknown'")

    is_valid = len(invented_items) == 0

    return ValidationResult(
        is_valid=is_valid,
        valid_evidence=valid_items,
        invented_evidence=invented_items,
        model_confidence=model_conf,
        evidence_score=evidence_score,
        calibrated_confidence=calibrated_conf,
        escalate_required=escalate,
        reason="; ".join(reasons) if reasons else "Diagnosis validated successfully",
    )
