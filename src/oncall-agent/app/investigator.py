import json
import logging
from typing import Any

from app.detector import Alert
from app.evidence import EvidenceLedger
from app.llm import LLMClient, llm_client
from app.tools.registry import TOOL_DEFINITIONS, execute_tool
from app.validator import validate_diagnosis

logger = logging.getLogger("oncall-agent.investigator")

SYSTEM_PROMPT = """You are an Autonomous SRE On-Call Engineer for the OpenTelemetry Astronomy Shop.
An incident alert has fired with symptoms. Your mission is to systematically investigate, locate the root cause, and submit a structured diagnosis.

SRE METHODOLOGY:
1. Examine the symptoms in the alert.
2. Formulate hypotheses about suspect services.
3. Follow failing traces to the DEEPEST failing dependency (the leaf error span, not an upstream caller that merely propagates an error).
4. Inspect that service's logs for exact error messages, exceptions, or failures.
5. Check container runtime health if a container is suspected down, restarting, or OOM-killed.
6. HARD RULE 1: Never search for, read, or cite feature flags or flagd state. Diagnosis must come strictly from telemetry and runtime health.
7. DECISIVENESS: As soon as you identify the root-cause service and confirm the failure via telemetry (failing trace or error logs), proceed directly to invoke 'submit_diagnosis'.
8. Submit your diagnosis using the 'submit_diagnosis' tool:
    - Every evidence item MUST cite the exact 'evidence_id' (e.g. E1, E2) returned by previous tool results.
    - The 'ref' field MUST contain an exact substring (trace ID, error message text, or metric snippet) that ACTUALLY appears in that evidence record.
    - Set 'confidence' realistically (e.g. 0.85-0.95 when confirmed by trace/logs).
    - Invented citations will be rejected by the deterministic validator.
"""

TOOL_TYPE_MAP = {
    "get_health_overview": "metric",
    "query_prometheus": "metric",
    "search_traces": "trace",
    "get_trace": "trace",
    "search_logs": "log",
    "get_container_health": "container",
    "get_recent_changes": "change",
    "search_incident_memory": "memory",
}


class InvestigationResult:
    def __init__(
        self,
        incident_id: str,
        diagnosis: dict[str, Any],
        validation_result: Any,
        steps_used: int,
        evidence_ledger: EvidenceLedger,
    ) -> None:
        self.incident_id = incident_id
        self.diagnosis = diagnosis
        self.validation = validation_result
        self.steps_used = steps_used
        self.ledger = evidence_ledger


class Investigator:
    def __init__(
        self,
        max_steps: int = 12,
        client: LLMClient | None = None,
    ) -> None:
        self.max_steps = max_steps
        self.client = client or llm_client

    def investigate(self, alert: Alert, ledger: EvidenceLedger | None = None) -> InvestigationResult:
        inc_id = alert.incident_id
        evidence_ledger = ledger or EvidenceLedger(inc_id)

        symptoms_summary = "\n".join(
            f"- [{s.type}] {s.service}: {s.description} (value={s.value}, threshold={s.threshold})"
            for s in alert.symptoms
        )
        user_prompt = (
            f"ALERT TRIGGERED for Incident {inc_id} at {alert.timestamp}:\n\n"
            f"Observed Symptoms:\n{symptoms_summary}\n\n"
            "Begin your investigation. Call tools sequentially, cite evidence IDs, and submit diagnosis when ready."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        steps = 0
        repair_attempted = False
        final_diagnosis: dict[str, Any] | None = None
        final_validation: Any = None

        while steps < self.max_steps:
            steps += 1
            try:
                response = self.client.chat(messages=messages, tools=TOOL_DEFINITIONS)
            except Exception as e:
                logger.error(f"LLM chat failure: {e}")
                break

            choice = response.choices[0]
            msg = choice.message
            tool_calls = getattr(msg, "tool_calls", None)

            # Append assistant message to history
            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if msg.content:
                assistant_msg["content"] = msg.content
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_msg)

            if not tool_calls:
                # If model responded with text instead of tool calls, prompt to proceed
                content = (msg.content or "").strip()
                if "submit_diagnosis" in content and "{" in content:
                    # Model attempted to write JSON diagnosis in text; instruct to use tool
                    messages.append({
                        "role": "user",
                        "content": "Please invoke the 'submit_diagnosis' function directly with your structured diagnosis.",
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": "You have analyzed the issue. Please invoke the 'submit_diagnosis' function directly with your structured diagnosis and evidence citations.",
                    })
                continue

            diagnosis_submitted = False
            for tc in tool_calls:
                fn_name = tc.function.name
                raw_args = tc.function.arguments
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except Exception:
                    args = {}

                if fn_name == "submit_diagnosis":
                    final_diagnosis = args
                    validation = validate_diagnosis(evidence_ledger, final_diagnosis)
                    final_validation = validation

                    if not validation.is_valid and not repair_attempted:
                        repair_attempted = True
                        repair_msg = (
                            f"Validation feedback on diagnosis:\n{validation.reason}\n"
                            "Some citations could not be verified in the evidence ledger. "
                            "Please repair your evidence citations and submit again."
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": repair_msg,
                        })
                        diagnosis_submitted = False
                        break
                    else:
                        diagnosis_submitted = True
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"Diagnosis accepted. Calibrated confidence: {validation.calibrated_confidence:.2f}.",
                        })
                        break

                ev_type = TOOL_TYPE_MAP.get(fn_name, "tool")
                raw_result = execute_tool(fn_name, args)
                eid = evidence_ledger.record_evidence(fn_name, args, raw_result, ev_type)

                tool_response_text = f"[Evidence ID: {eid}] (type: {ev_type})\n{raw_result}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_response_text,
                })

            if diagnosis_submitted:
                break

        if final_diagnosis is None:
            # Fallback diagnosis when max steps reached
            final_diagnosis = {
                "component": alert.symptoms[0].service if alert.symptoms else "unknown",
                "cause_category": "unknown",
                "cause_description": "Investigation reached max steps without conclusive root cause.",
                "confidence": 0.30,
                "evidence": [
                    {
                        "evidence_id": "E1",
                        "type": "metric",
                        "ref": alert.symptoms[0].description if alert.symptoms else "symptom",
                        "why_it_matters": "Observed symptom",
                    }
                ]
                if evidence_ledger.get_all_evidence()
                else [],
                "alternatives_considered": [],
                "recommended_runbook_ids": [],
            }
            final_validation = validate_diagnosis(evidence_ledger, final_diagnosis)

        return InvestigationResult(
            incident_id=inc_id,
            diagnosis=final_diagnosis,
            validation_result=final_validation,
            steps_used=steps,
            evidence_ledger=evidence_ledger,
        )


investigator = Investigator()
