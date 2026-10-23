import json
from typing import Any

VALID_CAUSE_CATEGORIES = {
    "service_fault_injected_errors",
    "dependency_unavailable",
    "container_down_or_crashloop",
    "resource_exhaustion_memory",
    "resource_exhaustion_cpu",
    "traffic_overload",
    "latency_degradation",
    "data_store_unavailable",
    "unknown",
}

VALID_EVIDENCE_TYPES = {
    "metric",
    "trace",
    "log",
    "container",
    "change",
    "memory",
}


def submit_diagnosis(
    component: str,
    cause_category: str,
    cause_description: str,
    confidence: float,
    evidence: list[dict[str, Any]],
    alternatives_considered: list[str] | None = None,
    recommended_runbook_ids: list[str] | None = None,
) -> str:
    if not component or not isinstance(component, str):
        return "Validation Error: 'component' must be a non-empty string."

    if cause_category not in VALID_CAUSE_CATEGORIES:
        return (
            f"Validation Error: 'cause_category' '{cause_category}' is invalid. "
            f"Must be one of: {sorted(VALID_CAUSE_CATEGORIES)}"
        )

    if not cause_description or not isinstance(cause_description, str):
        return "Validation Error: 'cause_description' must be a non-empty string."

    try:
        conf_float = float(confidence)
    except (TypeError, ValueError):
        return "Validation Error: 'confidence' must be a numeric value between 0.0 and 1.0."

    if not (0.0 <= conf_float <= 1.0):
        return f"Validation Error: 'confidence' {conf_float} must be between 0.0 and 1.0."

    if not isinstance(evidence, list) or len(evidence) == 0:
        return "Validation Error: 'evidence' must be a non-empty list of evidence citations."

    for idx, item in enumerate(evidence):
        if not isinstance(item, dict):
            return f"Validation Error: evidence[{idx}] must be a JSON object."
        for req_key in ("evidence_id", "type", "ref", "why_it_matters"):
            if req_key not in item:
                return f"Validation Error: evidence[{idx}] is missing required key '{req_key}'."
        ev_type = item.get("type")
        if ev_type not in VALID_EVIDENCE_TYPES:
            return (
                f"Validation Error: evidence[{idx}] type '{ev_type}' is invalid. "
                f"Must be one of: {sorted(VALID_EVIDENCE_TYPES)}"
            )

    diag_payload = {
        "component": component.strip(),
        "cause_category": cause_category,
        "cause_description": cause_description.strip(),
        "confidence": conf_float,
        "evidence": evidence,
        "alternatives_considered": alternatives_considered or [],
        "recommended_runbook_ids": recommended_runbook_ids or [],
    }

    out = (
        f"Diagnosis submitted successfully: component='{diag_payload['component']}', "
        f"category='{diag_payload['cause_category']}', confidence={diag_payload['confidence']:.2f}, "
        f"{len(evidence)} evidence citations verified."
    )
    return out
