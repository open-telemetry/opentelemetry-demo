"""Reviewer: a second model pass that tries to disprove the diagnosis before a human approves an action.

The reviewer gets the diagnosis, the citation verdicts and the stored transcript, and no tools, so it can
use only evidence already collected and cannot change anything. Its verdict is applied by fixed rules:
    upheld     confidence unchanged (a review never raises confidence)
    weakened   confidence lowered one level; reaching low escalates
    refuted    confidence capped at low and the incident escalates
    unavailable  the review failed or was unparseable after one retry; confidence unchanged, shown as such
Refs the reviewer cites must exist in the transcript's evidence; unknown refs are dropped and listed.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Sequence

from .guards import _ref_known, parse_json_object
from .llm import LLMError
from .transcript import Transcript

VERDICTS = ("upheld", "weakened", "refuted")
_LEVELS = ("low", "medium", "high")

REVIEWER_SYSTEM = """\
You are a skeptical incident reviewer. Try to disprove the diagnosis below using ONLY the stored tool \
results; you have no tools and must not ask for more data. Check:
1. Does each cited ref actually support the claim it is cited for?
2. Is there a better alternative root cause in the evidence?
3. Was a caller blamed when its calls to a failing or unreachable dependency never arrived?
4. Is the confidence justified by independent signals?

Verdict "upheld" if the diagnosis survives, "weakened" if it is plausible but over-confident or partly \
unsupported, "refuted" if the evidence contradicts it or points to another root cause.
Reply with ONE JSON object and nothing else:
{"verdict": "upheld|weakened|refuted", "reasons": ["..."], "better_alternative": "<service or null>", \
"refs": ["<refs from the tool results that back your reasons>"]}"""


def review_request(t: Transcript) -> str:
    verdicts = [{"ref": c.get("ref"), "valid": c.get("valid"), "reason": c.get("reason")}
                for c in t.citations or []]
    return (f"ALERT: {t.alert}\n\nDIAGNOSIS:\n{json.dumps(t.diagnosis, default=str)}\n\n"
            f"CITATION CHECKS:\n{json.dumps(verdicts, default=str)}\n\n"
            f"GATE: final confidence {(t.gate or {}).get('final_confidence')}\n\n"
            f"TOOL TRANSCRIPT (JSON):\n{t.compact_for_prompt()}\n\nReturn the review JSON now.")


def _check(text: str) -> tuple:
    obj, err = parse_json_object(text)
    if obj is None:
        return None, f"response is not a JSON object ({err})"
    if obj.get("verdict") not in VERDICTS:
        return None, f"verdict must be one of {list(VERDICTS)}"
    reasons = obj.get("reasons")
    if not isinstance(reasons, list) or not all(isinstance(r, str) for r in reasons):
        return None, "reasons must be a list of strings"
    if obj["verdict"] != "upheld" and not any(r.strip() for r in reasons):
        return None, f"a '{obj['verdict']}' verdict needs at least one reason"
    return obj, None


def review(t: Transcript, new_session: Callable[[str, Sequence[Dict[str, Any]]], Any]) -> Dict[str, Any]:
    """Run the reviewer once (plus one retry on invalid output). Never raises on model failure."""
    if not t.diagnosis or not (t.diagnosis.get("root_cause") or {}).get("service"):
        return {"verdict": "unavailable", "reasons": ["no diagnosis to review"], "better_alternative": None,
                "valid_refs": [], "invalid_refs": []}
    try:
        session = new_session(REVIEWER_SYSTEM, [])
        obj, problem = _check(session.send(user_text=review_request(t)).text)
        if obj is None:
            obj, problem = _check(session.send(
                user_text=f"Your review was rejected: {problem}. Return the corrected JSON object only.").text)
    except LLMError as e:
        obj, problem = None, f"reviewer LLM failure: {e}"
    if obj is None:
        return {"verdict": "unavailable", "reasons": [problem], "better_alternative": None,
                "valid_refs": [], "invalid_refs": []}
    idx = t.evidence_index()
    refs = [str(r) for r in obj.get("refs") or [] if str(r).strip()]
    alt = obj.get("better_alternative")
    return {"verdict": obj["verdict"], "reasons": [r.strip() for r in obj["reasons"] if r.strip()],
            "better_alternative": alt if isinstance(alt, str) and alt.strip() and alt != "null" else None,
            "valid_refs": [r for r in refs if _ref_known(r, idx)],
            "invalid_refs": [r for r in refs if not _ref_known(r, idx)]}


def apply_review(gate: Optional[Dict[str, Any]], result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new gate with the review applied. Confidence can only go down."""
    new = dict(gate or {"final_confidence": "low", "escalate": True})
    reasons: List[str] = list(new.get("reasons") or [])
    before = new.get("final_confidence") if new.get("final_confidence") in _LEVELS else "low"
    after = before
    verdict = result.get("verdict")
    if verdict == "refuted":
        after = "low"
        reasons.append("reviewer refuted the diagnosis: " + "; ".join(result.get("reasons") or [])[:300])
    elif verdict == "weakened":
        after = _LEVELS[max(0, _LEVELS.index(before) - 1)]
        reasons.append("reviewer weakened the diagnosis: " + "; ".join(result.get("reasons") or [])[:300])
    elif verdict == "unavailable":
        reasons.append("reviewer unavailable: " + "; ".join(result.get("reasons") or [])[:200])
    new.update(final_confidence=after, reasons=reasons, review=dict(result, confidence_before=before,
                                                                    confidence_after=after))
    if after == "low" or verdict == "refuted":
        new["escalate"] = True
    return new


def format_review(result: Dict[str, Any]) -> str:
    """Short text block shown to the human before the approval prompt."""
    lines = [f"Reviewer verdict: {str(result.get('verdict', 'unavailable')).upper()}"]
    if "confidence_before" in result:
        lines.append(f"  confidence {result['confidence_before']} -> {result['confidence_after']}")
    lines += [f"  - {r}" for r in result.get("reasons") or []]
    if result.get("better_alternative"):
        lines.append(f"  better alternative suggested: {result['better_alternative']}")
    if result.get("invalid_refs"):
        lines.append(f"  ignored refs not in the evidence: {', '.join(result['invalid_refs'])}")
    return "\n".join(lines)
