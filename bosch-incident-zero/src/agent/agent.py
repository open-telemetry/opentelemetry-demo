"""Two-phase incident agent: a bounded tool-calling investigation, then one diagnosis call."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..events import EventLog, scrub
from . import prompts
from .guards import (attribution_problems, confidence_gate, parse_json_object, schema_errors,
                     validate_citations)
from .llm import LLMError, LLMResponse, LLMSession, SessionFactory, ToolResultMessage
from .report import build_report, validate_report
from .reviewer import apply_review, review
from .tools import ToolBox
from .transcript import Transcript, utc_now

MAX_TOOL_CALLS = 12
MAX_MODEL_TURNS = 20


class IncidentAgent:
    def __init__(self, toolbox: ToolBox, new_session: SessionFactory,
                 max_tool_calls: int = MAX_TOOL_CALLS, output_dir: Optional[Path] = None,
                 events: Optional[EventLog] = None) -> None:
        self.toolbox = toolbox
        self.new_session = new_session
        self.max_tool_calls = max_tool_calls
        self.output_dir = output_dir
        self.events = events or EventLog(echo=False)

    def run(self, alert: str, incident_id: Optional[str] = None) -> Transcript:
        incident_id = incident_id or "INC-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        t = Transcript(incident_id=incident_id, alert=alert)
        self.events.bind(incident_id)
        self.events.emit("ALERT_RECEIVED", f"alert: {alert}", {"alert": alert})
        try:
            self._investigate(t)
            self._diagnose(t)
        except LLMError as e:
            t.errors.append(f"LLM failure: {e}")
            self.events.emit("ERROR", f"LLM failure: {str(e)[:200]}", {"source": "llm", "error": str(e)[:500]})
            if t.gate is None:
                t.gate = {"final_confidence": "low", "escalate": True, "reasons": [f"LLM failure: {e}"]}
        if t.diagnosis is not None:
            self._review(t)
        gate = t.gate or {}
        rev = gate.get("review") or {}
        verdict = f" review={rev['verdict']}" if rev else ""
        self.events.emit(
            "GATE", f"escalate={gate.get('escalate')} confidence={gate.get('final_confidence')}{verdict} "
                    f"tokens={t.token_usage['total_tokens']}",
            {"escalate": gate.get("escalate"), "final_confidence": gate.get("final_confidence"),
             "reasons": list(gate.get("reasons") or []), "token_usage": dict(t.token_usage),
             "review": {k: rev.get(k) for k in ("verdict", "reasons", "better_alternative",
                                                "confidence_before", "confidence_after")} if rev else None})
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
        resp = self._send(t, session, user_text=f"ALERT: {t.alert}\nCurrent time (UTC): {now}\nInvestigate.")
        turns = 1
        while resp.tool_calls and turns < MAX_MODEL_TURNS:
            if resp.text.strip():
                t.model_notes.append(resp.text.strip())
                self._note(resp.text.strip())
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
                self._tool_event(t.tool_calls[-1])
                results.append(ToolResultMessage(call.id, json.dumps(result, default=str),
                                                 result.get("status") == "error"))
            note = None
            if len(t.tool_calls) >= self.max_tool_calls:
                t.step_cap_hit = True
                note = "Tool budget exhausted. Reply now with your findings and do not call any tool."
            resp = self._send(t, session, tool_results=results, user_text=note)
            turns += 1
        t.findings = resp.text.strip()
        if t.findings:
            self._note(t.findings)
        if resp.tool_calls:
            t.errors.append("model kept requesting tools after the budget; investigation stopped")
            self.events.emit("ERROR", t.errors[-1], {"source": "agent"})

    # ---------------------------------------------------------------- phase 2

    def _diagnose(self, t: Transcript) -> None:
        session = self.new_session(prompts.diagnosis_system(), [])
        resp = self._send(t, session,
                          user_text=prompts.diagnosis_request(t.alert, t.findings, t.compact_for_prompt()))
        idx = t.evidence_index()
        diag, problems, citations = self._check(resp.text, idx)
        model = resp.model
        t.diagnosis_attempts.append({"raw": resp.text[:20000], "problems": problems})
        if problems:
            resp = self._send(t, session, user_text=prompts.diagnosis_retry(problems))
            retry_diag, retry_problems, retry_cites = self._check(resp.text, idx)
            t.diagnosis_attempts.append({"raw": resp.text[:20000], "problems": retry_problems})
            if retry_diag is not None:
                diag, problems, citations, model = retry_diag, retry_problems, retry_cites, resp.model

        if diag is None:
            t.errors.append("no parseable diagnosis after one retry: " + "; ".join(problems))
            self.events.emit("ERROR", t.errors[-1][:200], {"source": "llm", "error": t.errors[-1][:500]})
            diag = {"verdict": "escalate", "root_cause": {"service": "", "category": "unknown",
                                                          "summary": "Diagnosis output could not be parsed."},
                    "impacted_services": [], "severity": "MEDIUM", "confidence": "low", "evidence": [],
                    "alternatives": [], "recommended_next_step": "Escalate to on-call engineer with transcript."}
            citations = []
        t.diagnosis = diag
        t.citations = citations
        root = diag.get("root_cause") or {}
        self.events.emit(
            "DIAGNOSIS", f"{diag.get('verdict')}: {root.get('service') or '-'}/{root.get('category')} "
                         f"(model confidence {diag.get('confidence')})",
            {"verdict": diag.get("verdict"), "service": root.get("service"), "category": root.get("category"),
             "confidence": diag.get("confidence"), "model": model, "token_usage": dict(t.token_usage)})
        t.gate = confidence_gate(diag, citations, t)

    def _review(self, t: Transcript) -> None:
        def metered(system: str, tools: Any) -> LLMSession:
            return _MeteredSession(self.new_session(system, tools), t)

        try:
            result = review(t, metered)
        except Exception as e:
            result = {"verdict": "unavailable", "reasons": [f"reviewer failed: {type(e).__name__}: {e}"[:300]],
                      "better_alternative": None, "valid_refs": [], "invalid_refs": []}
        before = t.gate or {"final_confidence": "low", "escalate": True}
        after = apply_review(before, result)
        if before.get("escalate"):
            after["escalate"] = True
        t.gate = after

    def _note(self, text: str) -> None:
        self.events.emit("MODEL_NOTE", text[:200], {"text": text[:2000]})

    def _tool_event(self, call: Dict[str, Any]) -> None:
        result = call["result"]
        status, summary = result.get("status"), str(result.get("summary", ""))[:200]
        args = ", ".join(f"{k}={v}" for k, v in scrub(call["arguments"]).items())
        self.events.emit("TOOL_CALL", f"#{call['n']} {call['tool']}({args}) -> {status}: {summary}",
                         {"n": call["n"], "tool": call["tool"], "arguments": call["arguments"],
                          "status": status, "summary": summary})
        if status == "error":
            self.events.emit("ERROR", f"tool {call['tool']} failed: {summary}",
                             {"source": "tool", "tool": call["tool"], "error": summary})

    @staticmethod
    def _send(t: Transcript, session: LLMSession, **kwargs: Any) -> LLMResponse:
        resp = session.send(**kwargs)
        t.record_usage(resp.usage)
        t.record_model(resp.model)
        return resp

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


class _MeteredSession(LLMSession):
    def __init__(self, inner: LLMSession, t: Transcript) -> None:
        self.inner, self.t = inner, t

    def send(self, user_text: Optional[str] = None,
             tool_results: Optional[Sequence[ToolResultMessage]] = None) -> LLMResponse:
        return IncidentAgent._send(self.t, self.inner, user_text=user_text, tool_results=tool_results)
