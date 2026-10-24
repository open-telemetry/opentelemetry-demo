"""Two-phase incident agent: a bounded tool-calling investigation, then one diagnosis call."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import prompts
from .guards import (attribution_problems, confidence_gate, parse_json_object, schema_errors,
                     validate_citations)
from .llm import LLMError, SessionFactory, ToolResultMessage
from .report import build_report, validate_report
from .tools import ToolBox
from .transcript import Transcript, utc_now

MAX_TOOL_CALLS = 12
MAX_MODEL_TURNS = 20


class IncidentAgent:
    def __init__(self, toolbox: ToolBox, new_session: SessionFactory,
                 max_tool_calls: int = MAX_TOOL_CALLS, output_dir: Optional[Path] = None) -> None:
        self.toolbox = toolbox
        self.new_session = new_session
        self.max_tool_calls = max_tool_calls
        self.output_dir = output_dir

    def run(self, alert: str, incident_id: Optional[str] = None) -> Transcript:
        incident_id = incident_id or "INC-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        t = Transcript(incident_id=incident_id, alert=alert)
        try:
            self._investigate(t)
            self._diagnose(t)
        except LLMError as e:
            t.errors.append(f"LLM failure: {e}")
            if t.gate is None:
                t.gate = {"final_confidence": "low", "escalate": True, "reasons": [f"LLM failure: {e}"]}
        t.finished_at = utc_now()
        t.report = build_report(t)
        t.report_schema_valid, t.report_schema_errors = validate_report(t.report)
        if not t.report["evidence"]["trace_ids"]:
            t.report_schema_errors.append(
                "no validated trace ID, so evidence.trace_ids is empty; not filled with a placeholder")
        if self.output_dir:
            t.save(self.output_dir)
        return t

    # ---------------------------------------------------------------- phase 1

    def _investigate(self, t: Transcript) -> None:
        session = self.new_session(prompts.investigation_system(self.max_tool_calls), self.toolbox.specs)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        resp = session.send(user_text=f"ALERT: {t.alert}\nCurrent time (UTC): {now}\nInvestigate.")
        turns = 1
        while resp.tool_calls and turns < MAX_MODEL_TURNS:
            if resp.text.strip():
                t.model_notes.append(resp.text.strip())
            results: List[ToolResultMessage] = []
            for call in resp.tool_calls:
                if len(t.tool_calls) >= self.max_tool_calls:
                    t.step_cap_hit = True
                    results.append(ToolResultMessage(call.id, json.dumps(
                        {"status": "error", "summary": "Tool budget exhausted. Do not call more tools."}), True))
                    continue
                if call.invalid_arguments is not None:
                    result: Dict[str, Any] = {"tool": call.name, "status": "error",
                                              "summary": "Arguments were not valid JSON.", "data": {},
                                              "evidence": []}
                else:
                    result = self.toolbox.execute(call.name, call.arguments)
                t.record_tool(call.name, call.arguments, result)
                results.append(ToolResultMessage(call.id, json.dumps(result, default=str),
                                                 result.get("status") == "error"))
            note = None
            if len(t.tool_calls) >= self.max_tool_calls:
                t.step_cap_hit = True
                note = "Tool budget exhausted. Reply now with your findings and do not call any tool."
            resp = session.send(tool_results=results, user_text=note)
            turns += 1
        t.findings = resp.text.strip()
        if resp.tool_calls:
            t.errors.append("model kept requesting tools after the budget; investigation stopped")

    # ---------------------------------------------------------------- phase 2

    def _diagnose(self, t: Transcript) -> None:
        session = self.new_session(prompts.diagnosis_system(), [])
        resp = session.send(user_text=prompts.diagnosis_request(t.alert, t.findings, t.compact_for_prompt()))
        idx = t.evidence_index()
        diag, problems, citations = self._check(resp.text, idx)
        t.diagnosis_attempts.append({"raw": resp.text[:20000], "problems": problems})
        if problems:
            resp = session.send(user_text=prompts.diagnosis_retry(problems))
            retry_diag, retry_problems, retry_cites = self._check(resp.text, idx)
            t.diagnosis_attempts.append({"raw": resp.text[:20000], "problems": retry_problems})
            if retry_diag is not None:
                diag, problems, citations = retry_diag, retry_problems, retry_cites

        if diag is None:
            t.errors.append("no parseable diagnosis after one retry: " + "; ".join(problems))
            diag = {"verdict": "escalate", "root_cause": {"service": "", "category": "unknown",
                                                          "summary": "Diagnosis output could not be parsed."},
                    "impacted_services": [], "severity": "MEDIUM", "confidence": "low", "evidence": [],
                    "alternatives": [], "recommended_next_step": "Escalate to on-call engineer with transcript."}
            citations = []
        t.diagnosis = diag
        t.citations = citations
        t.gate = confidence_gate(diag, citations, t)

    @staticmethod
    def _check(text: str, idx) -> tuple:
        diag, err = parse_json_object(text)
        if diag is None:
            return None, [f"response is not a JSON object ({err})"], []
        problems = schema_errors(diag)
        citations = validate_citations(diag, idx)
        problems += [f"citation {c['ref']!r} rejected: {c['reason']}" for c in citations if not c["valid"]]
        problems += attribution_problems(diag, idx)
        return diag, problems, citations
