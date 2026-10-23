import os
import json
from typing import Callable, List, Dict, Any, Tuple, Optional
import anthropic

from Bosch.new.LLM_brain.agent.brain.models import (
    Incident,
    Evidence,
    Diagnosis,
    ConfidenceLabel,
    ToolStatus,
)

DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM_PROMPT = """You are an expert Autonomous Cloud-Native On-Call Site Reliability Engineer (SRE).
Your mission is to investigate an incident in the OpenTelemetry Demo microservices application, identify the root cause, and produce an evidence-backed diagnosis.

Service names in this application: frontend, frontend-proxy, cart, checkout, payment, product-catalog, recommendation, ad, shipping, currency, email, quote, valkey-cart (cache), load-generator. Use the names exactly as the tools expect them.

RULES:
1. Investigate systematically: start with the reported symptom/service, inspect traces to find child-span failures, then check metrics and logs. Use more than one source (traces, metrics, logs) before claiming high confidence.
2. DO NOT GUESS: every claim must be backed by evidence returned by your tools.
3. CITATION INTEGRITY: you may ONLY cite evidence IDs (e.g. 'ev-met-...' or 'ev-tra-...') that were explicitly returned to you in tool results with status OK. Never invent or predict an evidence ID.
4. FORBIDDEN ACCESS: never query feature-flag systems or flagd, and never try to read failure-flag settings. Reason from telemetry only.
5. Consider infrastructure causes (container stopped or restarting, cache or database unreachable, network latency or packet loss, CPU or memory starvation) as well as application faults, and combinations of several faults.
6. If evidence is weak, conflicting, or missing, set confidence to 'low' and recommend escalation to a human. A confident wrong answer is worse than escalating with your findings.
7. When you have sufficient evidence (or have exhausted useful checks), call the 'submit_diagnosis' tool to conclude.
"""

INVESTIGATION_TOOLS = [
    {
        "name": "query_traces",
        "description": "Queries Jaeger for distributed traces. Returns trace hops, error spans, and status codes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Microservice name (e.g., 'frontend', 'cart', 'payment', 'checkout')"},
                "num_traces": {"type": "integer", "description": "Number of traces to fetch (default 5)", "default": 5},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "query_metrics",
        "description": "Executes a PromQL query on Prometheus to get error rates, latency, or saturation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Service name to check metrics for"},
                "query": {"type": "string", "description": "PromQL query string"},
            },
            "required": ["service_name", "query"],
        },
    },
    {
        "name": "query_logs",
        "description": "Queries container logs for errors, exceptions, or specific keywords.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Container / service name"},
                "query_string": {"type": "string", "description": "Search keyword or error pattern"},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "submit_diagnosis",
        "description": "Submit the final evidence-backed diagnosis once the root cause is found, or when you must escalate. Concludes the investigation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "suspected_component": {"type": "string", "description": "Culprit service/component (e.g. 'cart', 'payment')"},
                "suspected_cause": {"type": "string", "description": "Clear explanation of the failure mechanism"},
                "supporting_evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Exact evidence_id strings (status OK) that support this diagnosis, copied from tool results",
                },
                "conflicting_evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Evidence IDs that contradict or disagree with this diagnosis, if any",
                },
                "alternatives": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Alternative hypotheses considered and ruled out",
                },
                "uncertainty": {"type": "string", "description": "Known unknowns, missing data, or limitations"},
                "confidence_label": {"type": "string", "enum": ["low", "medium", "high"]},
                "next_step": {"type": "string", "description": "Recommended safe remediation action, or escalation to a human"},
            },
            "required": [
                "suspected_component",
                "suspected_cause",
                "supporting_evidence_ids",
                "conflicting_evidence_ids",
                "alternatives",
                "uncertainty",
                "confidence_label",
                "next_step",
            ],
        },
    },
]

# Words that must never appear in tool arguments (organisers forbid reading flag settings)
_FORBIDDEN_TERMS = ("flagd", "feature-flag", "feature_flag", "featureflag", "feature flag")


class HarshitaBrain:
    def __init__(self, model: Optional[str] = None, max_turns: int = 8):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        self.max_turns = max_turns
        self._supports_temperature = True

    # ------------------------------------------------------------------ API
    def _create(self, **kwargs):
        """messages.create; safely falls back if temperature is rejected by SDK or API."""
        if not self._supports_temperature:
            return self.client.messages.create(**kwargs)

        try:
            return self.client.messages.create(temperature=0, **kwargs)
        except (TypeError, anthropic.BadRequestError) as e:
            if "temperature" in str(e).lower():
                self._supports_temperature = False
                return self.client.messages.create(**kwargs)
            raise

    # ------------------------------------------------------------ main loop
    def investigate(
        self,
        incident: Incident,
        telemetry_caller: Callable[[str, Dict[str, Any]], Evidence],
    ) -> Tuple[Diagnosis, List[Evidence]]:
        """
        Runs the bounded investigation loop.
        Returns (Diagnosis, collected_evidence_list)
        """
        collected_evidence: List[Evidence] = []
        valid_ids: set = set()             # every ID a tool returned
        ok_ids: set = set()                # IDs with status OK (allowed to support a diagnosis)
        source_by_id: Dict[str, str] = {}  # evidence_id -> source (jaeger/prometheus/...)

        initial_user_msg = (
            f"ALERT TRIGGERED:\n"
            f"- Incident ID: {incident.id}\n"
            f"- Symptom: {incident.symptom}\n"
            f"- Suspected/Affected Service: {incident.affected_service}\n"
            f"- Detection Time: {incident.detection_time.isoformat()}\n"
            f"- Observation Window: {incident.observation_window.start_time.isoformat()} "
            f"to {incident.observation_window.end_time.isoformat()}\n"
            f"- Recovery Target: {incident.recovery_condition}\n\n"
            f"Please investigate the root cause by calling appropriate telemetry tools."
        )

        messages: list = [{"role": "user", "content": initial_user_msg}]
        final_diagnosis: Optional[Diagnosis] = None

        for _ in range(self.max_turns):
            response = self._create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=INVESTIGATION_TOOLS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_calls = [c for c in response.content if c.type == "tool_use"]
            if not tool_calls:
                break  # text-only reply; a diagnosis is forced below

            submission = next((tc for tc in tool_calls if tc.name == "submit_diagnosis"), None)
            if submission:
                final_diagnosis = self._build_and_sanitize_diagnosis(
                    submission.input, valid_ids, ok_ids, source_by_id
                )
                break

            tool_results = []
            for tc in tool_calls:
                content, is_error = self._run_tool(
                    tc, telemetry_caller, collected_evidence, valid_ids, ok_ids, source_by_id
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": content,
                    "is_error": is_error,
                })
            messages.append({"role": "user", "content": tool_results})

        if final_diagnosis is None:
            final_diagnosis = self._force_diagnosis_submission(messages, valid_ids, ok_ids, source_by_id)

        return final_diagnosis, collected_evidence

    # ----------------------------------------------------------- tool runner
    def _run_tool(self, tc, telemetry_caller, collected, valid_ids, ok_ids, source_by_id):
        """Runs one telemetry tool safely. Returns (tool_result_content, is_error)."""
        args = dict(tc.input or {})

        # Code-level enforcement of the "no flagd / feature flags" rule
        if any(term in json.dumps(args, default=str).lower() for term in _FORBIDDEN_TERMS):
            return ("Blocked: querying flagd or feature-flag settings is not allowed. "
                    "Investigate using traces, metrics and logs only."), True

        try:
            ev: Evidence = telemetry_caller(tc.name, args)
        except Exception as e:  # tool crash must not kill the investigation
            return f"Tool '{tc.name}' failed: {type(e).__name__}: {e}", True

        collected.append(ev)
        valid_ids.add(ev.evidence_id)
        source_by_id[ev.evidence_id] = str(getattr(ev, "source", "unknown"))
        if ev.status == ToolStatus.OK:
            ok_ids.add(ev.evidence_id)

        content = json.dumps({
            "evidence_id": ev.evidence_id,
            "status": ev.status.value,
            "tool": ev.tool,
            "source": getattr(ev, "source", None),
            "service": getattr(ev, "service", None),
            "observed_value": ev.observed_value,
            "trace_or_log_id": ev.trace_or_log_id,
        }, default=str)
        return content, False

    # ---------------------------------------------------- citation integrity
    def _build_and_sanitize_diagnosis(
        self,
        raw_args: dict,
        valid_ids: set,
        ok_ids: set,
        source_by_id: Dict[str, str],
    ) -> Diagnosis:
        """
        CITATION INTEGRITY GATE.
        - Only evidence the model cited AND that exists with status OK can support the diagnosis.
        - Invalid citations are removed and force low confidence.
        - No valid support => low confidence + escalation (never padded with random IDs).
        - High confidence needs support from at least 2 different sources.
        """
        cited_support = list(raw_args.get("supporting_evidence_ids", []) or [])
        cited_conflict = list(raw_args.get("conflicting_evidence_ids", []) or [])

        supporting = [e for e in cited_support if e in ok_ids]
        conflicting = [e for e in cited_conflict if e in valid_ids]
        dropped = (len(cited_support) - len(supporting)) + (len(cited_conflict) - len(conflicting))

        conf = str(raw_args.get("confidence_label", "low")).lower()
        if conf not in ("low", "medium", "high"):
            conf = "low"

        uncertainty = str(raw_args.get("uncertainty", "") or "")
        next_step = str(raw_args.get("next_step", "") or "Escalate to human engineer")

        if not supporting:
            conf = "low"
            uncertainty = (uncertainty + " [Gate: no valid supporting evidence.]").strip()
            next_step = "Escalate to human engineer with findings"
        elif dropped:
            conf = "low"
            uncertainty = (uncertainty + f" [Gate: {dropped} invalid citation(s) removed.]").strip()
        elif conf == "high" and len({source_by_id.get(e) for e in supporting}) < 2:
            conf = "medium"
            uncertainty = (uncertainty + " [Gate: high confidence needs 2+ independent sources.]").strip()

        return Diagnosis(
            suspected_component=raw_args.get("suspected_component", "unknown"),
            suspected_cause=raw_args.get("suspected_cause", "Undetermined failure mechanism"),
            supporting_evidence_ids=supporting,
            conflicting_evidence_ids=conflicting,
            alternatives=raw_args.get("alternatives", []) or [],
            uncertainty=uncertainty or "None stated",
            confidence_label=ConfidenceLabel(conf),
            next_step=next_step,
        )

    # --------------------------------------------------- forced submission
    def _force_diagnosis_submission(
        self,
        messages: list,
        valid_ids: set,
        ok_ids: set,
        source_by_id: Dict[str, str],
    ) -> Diagnosis:
        """Forces submit_diagnosis when the turn budget is exhausted or the model replied with text only."""
        force_block = {
            "type": "text",
            "text": (
                "Investigation limit reached. Call submit_diagnosis now. "
                f"Only cite these evidence IDs: {sorted(ok_ids)}. "
                "If evidence is insufficient or conflicting, use confidence 'low' and recommend escalation to a human."
            ),
        }
        # Merge into the trailing user message (tool results) so roles keep alternating
        if messages and messages[-1]["role"] == "user" and isinstance(messages[-1]["content"], list):
            messages[-1]["content"].append(force_block)
        else:
            messages.append({"role": "user", "content": [force_block]})

        try:
            response = self._create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=INVESTIGATION_TOOLS,  # full list so earlier tool_use blocks stay valid
                tool_choice={"type": "tool", "name": "submit_diagnosis"},
                messages=messages,
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "submit_diagnosis":
                    return self._build_and_sanitize_diagnosis(block.input, valid_ids, ok_ids, source_by_id)
        except Exception:
            pass  # fall through to the safe fallback

        return Diagnosis(
            suspected_component="unknown",
            suspected_cause="Investigation budget exhausted without definitive root cause",
            supporting_evidence_ids=[],
            conflicting_evidence_ids=[],
            alternatives=["Telemetry timeout", "Cascade failure"],
            uncertainty="Could not reach conclusive evidence within the step limit",
            confidence_label=ConfidenceLabel.LOW,
            next_step="Escalate incident to human engineer",
        )