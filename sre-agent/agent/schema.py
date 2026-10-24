"""Diagnosis output schema.

Internal model = `Diagnosis` (pydantic, always validated).
Official output = `to_official(diagnosis)` -> dict in the ORGANISERS' format.

>>> TO ADAPT TO THE OFFICIAL SCHEMA (5 min):
  1. copy their JSON-schema file to config/output_schema.json   (it is then enforced automatically)
  2. edit ONLY `to_official()` below so field names / enums match theirs.
  3. run `python -m agent.main schema-check runs/<id>/diagnosis.json`
"""
import json
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from agent import config
from agent.rules import FAULT_TYPES

FaultType = Literal[tuple(FAULT_TYPES)]
Source = Literal["metrics", "traces", "logs", "runtime"]


class Evidence(BaseModel):
    source: Source
    signal: str = Field(description="what was observed, quoting the number / message")
    reference: Optional[str] = Field(None, description="exact trace ID, log line or metric value as seen in a tool result")
    supports: str = Field("", description="why this points to the root cause")
    tool_call: Optional[int] = Field(None, description="number of the tool call that returned it")
    verified: Optional[bool] = Field(None, description="set by the agent's evidence checker, not by the LLM")


class RootCause(BaseModel):
    service: str
    component: Optional[str] = Field(None, description="operation / endpoint / dependency link, if known")
    fault_type: FaultType
    summary: str = Field(description="one sentence root cause")


class Diagnosis(BaseModel):
    incident_id: str
    detected_at: str
    status: Literal["diagnosed", "escalated", "no_incident"] = "diagnosed"
    root_cause: RootCause
    confidence: float = Field(ge=0, le=1)
    evidence: List[Evidence] = Field(min_length=1)
    affected_services: List[str] = []
    alternative_hypotheses: List[str] = []
    reasoning: str = ""
    escalation_reason: Optional[str] = None


def llm_submit_schema() -> dict:
    """JSON schema of what the LLM must submit (no ids/timestamps/verified - the agent fills those)."""
    s = Diagnosis.model_json_schema()
    for k in ("incident_id", "detected_at", "status", "escalation_reason"):
        s["properties"].pop(k, None)
        if k in s.get("required", []):
            s["required"].remove(k)
    ev = s["$defs"]["Evidence"]["properties"]
    ev.pop("verified", None)
    return s


def to_official(d: dict, extra: dict = None) -> dict:
    """Map the internal diagnosis to the organisers' JSON schema. EDIT THIS to match their fields."""
    extra = extra or {}
    rc = d["root_cause"]
    return {
        "incident_id": d["incident_id"],
        "detected_at": d["detected_at"],
        "status": d["status"],
        "root_cause": {"service": rc["service"], "component": rc.get("component"),
                       "fault_type": rc["fault_type"], "summary": rc["summary"]},
        "confidence": d["confidence"],
        "evidence": [{k: e.get(k) for k in ("source", "signal", "reference", "supports")}
                     for e in d["evidence"] if e.get("verified") is not False],
        "affected_services": d.get("affected_services", []),
        "alternative_hypotheses": d.get("alternative_hypotheses", []),
        "escalation_reason": d.get("escalation_reason") or {
            "rejected": "Human rejected the proposed action.",
            "not_recovered": "Action executed but recovery was not verified - escalated with findings.",
            "action_failed": "Action API call failed - escalated.",
            "killed": "Kill switch engaged - no action executed."}.get(extra.get("outcome")),
        "outcome": extra.get("outcome"),
        "proposed_action": extra.get("proposed_action"),
        "action_taken": extra.get("action_taken"),
        "recovery_verified": extra.get("recovery_verified"),
    }


def validate_official(obj: dict) -> list:
    """Returns a list of problems ([] = valid). Uses config/output_schema.json when present."""
    if not config.OUTPUT_SCHEMA_FILE.exists():
        return []
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed - pip install jsonschema"]
    schema = json.loads(config.OUTPUT_SCHEMA_FILE.read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in v.iter_errors(obj)]
