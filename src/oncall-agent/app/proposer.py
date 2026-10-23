from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel

from app.llm import LLMClient, llm_client
from app.runbook import RunbookEntry, find_matching_runbooks, resolve_params

logger = logging.getLogger("oncall-agent.proposer")


class Proposal(BaseModel):
    runbook_id: str
    action: str
    params: dict[str, Any]
    reason: str
    expected_recovery_signal: str
    rollback_plan: str | None = None


PROPOSER_SYSTEM = """You are an SRE deciding which remediation runbook to apply.
Given a diagnosis and a list of candidate runbook entries, choose the single best match.
Respond in JSON exactly: {"runbook_id": "<id>", "reason": "<one sentence why>"}.
Choose the least-invasive option that directly addresses the root cause.
Only choose a runbook from the provided candidate list. Never invent a new runbook."""


class Proposer:
    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or llm_client

    def propose(
        self,
        diagnosis: dict[str, Any],
        incident_id: str,
    ) -> list[Proposal]:
        component = diagnosis.get("component", "unknown")
        category = diagnosis.get("cause_category", "unknown")
        description = diagnosis.get("cause_description", "")

        candidates = find_matching_runbooks(category, component)

        if not candidates:
            logger.warning(
                "No matching runbooks for category=%s component=%s — escalating",
                category,
                component,
            )
            return []

        # For clarity/safety: build a compact candidate summary for the LLM
        candidates_text = "\n".join(
            f"  - {rb.id}: {rb.description} [action={rb.action}, risk={rb.risk}]"
            for rb in candidates
        )

        user_msg = (
            f"Incident {incident_id}\n"
            f"Diagnosed component: {component}\n"
            f"Cause category: {category}\n"
            f"Description: {description}\n\n"
            f"Candidate runbooks:\n{candidates_text}\n\n"
            "Choose the best runbook. Respond only with JSON."
        )

        messages = [
            {"role": "system", "content": PROPOSER_SYSTEM},
            {"role": "user", "content": user_msg},
        ]

        chosen_id: str | None = None
        reason: str = ""

        try:
            response = self.client.chat(messages=messages, tools=None)
            raw = (response.choices[0].message.content or "").strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"```[a-z]*\n?", "", raw).rstrip("`").strip()
            payload = json.loads(raw)
            chosen_id = str(payload.get("runbook_id", "")).strip()
            reason = str(payload.get("reason", "")).strip()
        except Exception as e:
            logger.error("Proposer LLM call failed: %s", e)

        # Validate: must be in candidate list
        candidate_ids = {rb.id for rb in candidates}
        if chosen_id not in candidate_ids:
            # Fall back to first candidate (least-invasive)
            chosen_id = candidates[0].id
            reason = f"LLM selection invalid or failed; defaulting to least-invasive: {candidates[0].description}"
            logger.warning("Proposer: LLM chose invalid runbook '%s', falling back to %s", chosen_id, candidates[0].id)

        # Build Proposal for each applicable runbook action (chosen first, then remaining if combined faults)
        proposals: list[Proposal] = []
        for rb in candidates:
            if rb.id == chosen_id:
                resolved = resolve_params(rb, component)
                proposals.append(
                    Proposal(
                        runbook_id=rb.id,
                        action=rb.action,
                        params=resolved,
                        reason=reason or rb.reason_template,
                        expected_recovery_signal=rb.expected_recovery_signal,
                        rollback_plan=rb.rollback_action,
                    )
                )
                break

        if not proposals:
            # Construct from first candidate as fallback
            rb = candidates[0]
            proposals.append(
                Proposal(
                    runbook_id=rb.id,
                    action=rb.action,
                    params=resolve_params(rb, component),
                    reason=rb.reason_template,
                    expected_recovery_signal=rb.expected_recovery_signal,
                    rollback_plan=rb.rollback_action,
                )
            )

        return proposals


proposer = Proposer()
