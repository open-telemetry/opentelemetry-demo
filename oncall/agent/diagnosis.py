"""Diagnosis step: turn a finished investigation into a structured Diagnosis."""

import json
from typing import get_args

from oncall.agent import taxonomy
from oncall.agent.llm import LLM, LLMError
from oncall.agent.prompts import DIAGNOSE
from oncall.agent.runlog import RunLog
from oncall.models import Alert, Category, Diagnosis

SUBMIT = "submit_diagnosis"
MAX_REASONING_CHARS = 800
MAX_ATTEMPTS = 2
CATEGORY_NAMES = list(get_args(Category))
DECISIONS = ["act", "escalate"]

SUBMIT_SCHEMA = {
    "name": SUBMIT,
    "description": "Submit the structured diagnosis of the incident.",
    "input_schema": {
        "type": "object",
        "properties": {
            "component": {
                "type": ["string", "null"],
                "description": "Root-cause service or container, or null if unknown.",
            },
            "category": {"type": "string", "enum": CATEGORY_NAMES},
            "cause": {"type": "string", "description": "One specific sentence."},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "affected_services": {"type": "array", "items": {"type": "string"}},
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hypothesis": {"type": "string"},
                        "rejected_because": {"type": "string"},
                    },
                    "required": ["hypothesis", "rejected_because"],
                },
            },
            "decision": {"type": "string", "enum": DECISIONS},
            "reasoning": {"type": "string"},
        },
        "required": [
            "component",
            "category",
            "cause",
            "confidence",
            "evidence_ids",
            "affected_services",
            "alternatives",
            "decision",
            "reasoning",
        ],
    },
}


def escalate_unknown(reason: str, affected: list[str] | None = None) -> Diagnosis:
    """The safe fallback: no component, category unknown, escalate to a human."""
    return {
        "component": None,
        "category": "unknown",
        "cause": "Could not determine the root cause.",
        "confidence": 0.0,
        "evidence_ids": [],
        "affected_services": list(affected or []),
        "alternatives": [],
        "decision": "escalate",
        "reasoning": reason[:MAX_REASONING_CHARS],
    }


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def check(raw: object) -> list[str]:
    """Problems with a submit_diagnosis payload; empty when it is valid."""
    if not isinstance(raw, dict):
        return ["the diagnosis must be a JSON object"]
    problems = []
    missing = [k for k in SUBMIT_SCHEMA["input_schema"]["required"] if k not in raw]
    if missing:
        problems.append(f"missing fields: {', '.join(missing)}")
    if "component" in raw and not (
        raw["component"] is None or isinstance(raw["component"], str)
    ):
        problems.append("component must be a string or null")
    if "category" in raw and raw["category"] not in CATEGORY_NAMES:
        problems.append(f"category must be one of: {', '.join(CATEGORY_NAMES)}")
    if "decision" in raw and raw["decision"] not in DECISIONS:
        problems.append("decision must be 'act' or 'escalate'")
    if "confidence" in raw:
        c = raw["confidence"]
        if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
            problems.append("confidence must be a number from 0 to 1")
    for key in ("cause", "reasoning"):
        if key in raw and not isinstance(raw[key], str):
            problems.append(f"{key} must be a string")
    for key in ("evidence_ids", "affected_services"):
        if key in raw and not _is_str_list(raw[key]):
            problems.append(f"{key} must be a list of strings")
    if "alternatives" in raw:
        alts = raw["alternatives"]
        if not isinstance(alts, list) or not all(
            isinstance(a, dict)
            and isinstance(a.get("hypothesis"), str)
            and isinstance(a.get("rejected_because"), str)
            for a in alts
        ):
            problems.append(
                "alternatives must be a list of {hypothesis, rejected_because} strings"
            )
    return problems


def _post_check(raw: dict) -> Diagnosis:
    """Normalise a valid payload and enforce the rules the LLM may not break."""
    d: Diagnosis = {
        "component": raw["component"] or None,
        "category": raw["category"],
        "cause": raw["cause"],
        "confidence": float(raw["confidence"]),
        "evidence_ids": list(dict.fromkeys(raw["evidence_ids"])),
        "affected_services": list(dict.fromkeys(raw["affected_services"])),
        "alternatives": [
            {"hypothesis": a["hypothesis"], "rejected_because": a["rejected_because"]}
            for a in raw["alternatives"]
        ],
        "decision": raw["decision"],
        "reasoning": raw["reasoning"],
    }
    if d["component"] in taxonomy.CLIENT_SERVICES:
        client = d["component"]
        d["component"] = None
        d["decision"] = "escalate"
        if client not in d["affected_services"]:
            d["affected_services"].append(client)
        d["reasoning"] = (
            f"[post-check: {client} is a client, so it cannot be the root cause] "
            + d["reasoning"]
        )
    d["reasoning"] = d["reasoning"][:MAX_REASONING_CHARS]
    return d


def _tool_log(run: RunLog) -> str:
    lines = []
    for i, e in enumerate(run.events("tool_result"), 1):
        r = e.get("result") or {}
        status = "ok" if r.get("ok") else f"error: {r.get('error')}"
        lines.append(
            f"{i}. {e.get('name')}({json.dumps(r.get('query', {}))}) -> {status}: "
            f"{r.get('summary', '')}"
        )
    return "\n".join(lines) or "(no tool calls)"


def _evidence(run: RunLog) -> str:
    items = run.evidence_index().values()
    return "\n".join(f"- {e['id']}: {e.get('text', '')}" for e in items) or "(none)"


def _summary(run: RunLog) -> str:
    finishes = run.events("finish")
    return (finishes[-1].get("summary") if finishes else "") or "(no summary)"


def build_prompt(run: RunLog, alert: Alert) -> str:
    return DIAGNOSE.format(
        alert_id=alert["id"],
        alert_ts=alert["ts"],
        alert_service=alert["service"],
        alert_signal=alert["signal"],
        alert_description=alert["description"],
        summary=_summary(run),
        tool_log=_tool_log(run),
        evidence=_evidence(run),
        taxonomy=taxonomy.render(),
    )


def diagnose(run: RunLog, alert: Alert, llm: LLM) -> Diagnosis:
    """Ask the LLM for a Diagnosis via a forced submit_diagnosis call.

    One retry on invalid output; after that, or on an LLM error, return an
    escalate Diagnosis with category "unknown". Never raises.
    """
    affected = [alert["service"]] if alert.get("service") else []
    messages = [{"role": "user", "content": build_prompt(run, alert)}]
    problems: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            reply = llm.chat(messages, [SUBMIT_SCHEMA])
        except LLMError as exc:
            run.log("error", where="diagnose", attempt=attempt, error=str(exc))
            d = escalate_unknown(f"LLM call failed during diagnosis: {exc}", affected)
            run.log("decision", diagnosis=d, valid=False)
            return d
        run.log("llm_call", step="diagnose", attempt=attempt, usage=reply.usage)

        calls = [c for c in reply.tool_calls if c["name"] == SUBMIT]
        if not calls:
            problems = [f"you must call {SUBMIT}; got no {SUBMIT} call"]
        elif calls[0]["args"] is None:
            problems = [calls[0].get("error", "arguments missing")]
        else:
            problems = check(calls[0]["args"])
        if not problems:
            d = _post_check(calls[0]["args"])
            run.log("decision", diagnosis=d, valid=True, attempt=attempt)
            return d

        run.log("error", where="diagnose", attempt=attempt, problems=problems)
        messages.append(
            {
                "role": "user",
                "content": f"Your diagnosis was invalid: {'; '.join(problems)}. "
                f"Call {SUBMIT} again with every field valid.",
            }
        )

    d = escalate_unknown(
        f"Diagnosis output invalid after {MAX_ATTEMPTS} attempts: {'; '.join(problems)}",
        affected,
    )
    run.log("decision", diagnosis=d, valid=False)
    return d
