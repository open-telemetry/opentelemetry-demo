"""Output guards: diagnosis shape, evidence-citation validation and the confidence gate."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

from .transcript import EvidenceIndex, Transcript

CATEGORIES = [
    "errors_on_operation", "latency_without_errors", "memory_growth", "cpu_saturation",
    "container_down_or_restarting", "dependency_unreachable", "queue_lag", "traffic_spike", "unknown",
]
SIGNAL_KINDS = ("trace", "metric", "log", "container")

DIAGNOSIS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["verdict", "root_cause", "confidence", "severity", "evidence", "alternatives",
                 "impacted_services", "recommended_next_step"],
    "properties": {
        "verdict": {"enum": ["diagnosed", "escalate"]},
        "root_cause": {
            "type": "object", "required": ["service", "category", "summary"],
            "properties": {"service": {"type": "string"}, "category": {"enum": CATEGORIES},
                           "operation": {"type": ["string", "null"]}, "summary": {"type": "string"}}},
        "impacted_services": {"type": "array", "items": {"type": "string"}},
        "severity": {"enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
        "confidence": {"enum": ["high", "medium", "low"]},
        "evidence": {"type": "array", "items": {
            "type": "object", "required": ["kind", "ref"],
            "properties": {"kind": {"enum": list(SIGNAL_KINDS)}, "ref": {"type": "string"},
                           "value": {}, "quote": {"type": ["string", "null"]},
                           "supports": {"type": ["string", "null"]}}}},
        "alternatives": {"type": "array", "items": {
            "type": "object", "required": ["hypothesis", "status", "reason"],
            "properties": {"hypothesis": {"type": "string"}, "status": {"enum": ["ruled_out", "possible"]},
                           "reason": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}}}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "recommended_next_step": {"type": "string"},
    },
}

# A bare 32-hex token in prose looks like a trace ID and must also be backed by tool output.
_TRACE_LIKE = re.compile(r"\b[0-9a-f]{32}\b", re.IGNORECASE)
_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def parse_json_object(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Extract the first JSON object from a model reply (plain or inside a ``` fence)."""
    if not text or not text.strip():
        return None, "empty response"
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj, None
        except ValueError as e:
            err = f"invalid JSON: {e}"
    return None, locals().get("err", "no JSON object found")


def schema_errors(diag: Dict[str, Any]) -> List[str]:
    validator = jsonschema.Draft202012Validator(DIAGNOSIS_SCHEMA)
    return [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in validator.iter_errors(diag)][:10]


def _num_match(claimed: Any, stored: List[Any]) -> bool:
    try:
        c = float(claimed)
    except (TypeError, ValueError):
        return str(claimed) in {str(s) for s in stored}
    for s in stored:
        try:
            v = float(s)
        except (TypeError, ValueError):
            continue
        if abs(c - v) <= max(1e-6, 0.02 * abs(v)):
            return True
    return False


def validate_citations(diag: Dict[str, Any], idx: EvidenceIndex) -> List[Dict[str, Any]]:
    """Check every cited item against stored tool results. Returns one verdict per citation."""
    results: List[Dict[str, Any]] = []
    for item in diag.get("evidence", []) or []:
        kind, ref = item.get("kind"), str(item.get("ref", "")).strip()
        ok, reason = False, ""
        if kind == "trace":
            r = ref.lower()
            if r.startswith("span:"):
                ok = r in idx.span_refs
            else:
                ok = r in idx.trace_ids
            reason = "" if ok else "trace/span ID not present in any tool result"
        elif kind == "log":
            if ref in idx.logs:
                quote = item.get("quote")
                ok = not quote or str(quote).strip() in idx.logs[ref]
                reason = "" if ok else "quoted text does not match the stored log line"
            else:
                reason = "log ref not present in any tool result"
        elif kind == "metric":
            if ref in idx.metrics:
                ok = item.get("value") is None or _num_match(item.get("value"), idx.metrics[ref])
                reason = "" if ok else f"value {item.get('value')} does not match stored {idx.metrics[ref]}"
            else:
                reason = "metric ref not present in any tool result"
        elif kind == "container":
            if ref in idx.containers:
                ok = item.get("value") is None or _num_match(item.get("value"), idx.containers[ref])
                reason = "" if ok else f"value {item.get('value')} does not match stored {idx.containers[ref]}"
            else:
                reason = "container ref not present in any tool result"
        else:
            reason = f"unknown evidence kind '{kind}'"
        results.append({"kind": kind, "ref": ref, "valid": ok, "reason": reason})

    prose = " ".join([str((diag.get("root_cause") or {}).get("summary", ""))] +
                     [str(a.get("reason", "")) for a in diag.get("alternatives", []) or []])
    for tok in set(_TRACE_LIKE.findall(prose)):
        if tok.lower() not in idx.trace_ids:
            results.append({"kind": "trace", "ref": tok, "valid": False,
                            "reason": "trace-like ID in prose not present in any tool result"})
    return results


def attribution_problems(diag: Dict[str, Any], idx: EvidenceIndex) -> List[str]:
    """Flag a root cause that names the caller when the traces show its calls never reached a
    dependency. The unreachable dependency is the root cause; the caller is impacted."""
    root = str((diag.get("root_cause") or {}).get("service", "")).strip()
    if not root or diag.get("verdict") == "escalate":
        return []
    deps = sorted({d for c, d in idx.unreached if c == root})
    if not deps or any(d == root for _, d in idx.unreached):
        return []
    return [f"root_cause.service is '{root}', but the traces show {root}'s failing calls to "
            f"{', '.join(deps)} never reached {', '.join(deps)} (no span from the dependency). The "
            f"unreachable dependency is the root cause (category dependency_unreachable); list '{root}' "
            f"and its callers under impacted_services, or escalate if you believe otherwise."]



def _ref_known(ref: str, idx: EvidenceIndex) -> bool:
    r = str(ref).strip()
    low = r.lower()
    if low.startswith("span:"):
        return low in idx.span_refs
    if r.startswith("metric:"):
        return r in idx.metrics
    if r.startswith("container:"):
        return r in idx.containers
    if r.startswith("log:"):
        return r in idx.logs
    return low in idx.trace_ids


def confidence_gate(diag: Dict[str, Any], citations: List[Dict[str, Any]],
                    transcript: Transcript) -> Dict[str, Any]:
    """Deterministic ceiling on confidence; decides escalation.

    high   = two independent signal kinds validated + one alternative ruled out with at least one
             cited ref that exists in the tool results + no invalid citations
    medium = one validated signal kind with at least one more validated item as context
    low    = anything else, which escalates to a human with the findings
    """
    valid = [c for c in citations if c["valid"]]
    invalid = [c for c in citations if not c["valid"]]
    kinds = sorted({c["kind"] for c in valid if c["kind"] in SIGNAL_KINDS})
    idx = transcript.evidence_index()
    alt_checked = any(
        a.get("status") == "ruled_out" and str(a.get("reason", "")).strip()
        and a.get("refs") and all(_ref_known(r, idx) for r in a["refs"])
        for a in diag.get("alternatives", []) or [])
    reasons: List[str] = []

    if len(kinds) >= 2 and alt_checked and not invalid:
        allowed = "high"
    elif len(kinds) >= 1 and len(valid) >= 2:
        allowed = "medium"
        if len(kinds) < 2:
            reasons.append("only one independent signal type is backed by validated evidence")
        if not alt_checked:
            reasons.append("no alternative cause was ruled out with cited evidence")
        if invalid:
            reasons.append(f"{len(invalid)} citation(s) failed validation")
    else:
        allowed = "low"
        reasons.append(f"only {len(valid)} validated evidence item(s) across {len(kinds)} signal type(s)")

    claimed = diag.get("confidence", "low")
    final = claimed if _CONFIDENCE_RANK.get(claimed, 0) <= _CONFIDENCE_RANK[allowed] else allowed
    if final != claimed:
        reasons.append(f"confidence lowered from {claimed} to {final}")

    statuses = [c["result"].get("status") for c in transcript.tool_calls]
    if statuses and all(s in ("source_unavailable", "error") for s in statuses):
        final = "low"
        reasons.append("every telemetry source was unavailable or errored")

    misattributed = attribution_problems(diag, idx)
    if misattributed:
        final = "low"
        reasons.append("root cause names the caller of an unreachable dependency")

    root = (diag.get("root_cause") or {}).get("service", "")
    escalate = (final == "low" or diag.get("verdict") == "escalate" or not root
                or (diag.get("root_cause") or {}).get("category") == "unknown")
    if diag.get("verdict") == "escalate":
        reasons.append("the model chose to escalate")
    return {"allowed_confidence": allowed, "claimed_confidence": claimed, "final_confidence": final,
            "escalate": escalate, "validated_signal_kinds": kinds, "alternative_ruled_out": alt_checked,
            "valid_citations": len(valid), "invalid_citations": len(invalid), "reasons": reasons}
