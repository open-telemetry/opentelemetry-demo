from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from oncall.agent.prompts import FINAL_REMINDER, SYSTEM_PROMPT
from oncall.events import EventLog
from oncall.ledger import EvidenceLedger
from oncall.schema import Diagnosis
from oncall.tools import REGISTRY, load_all

MAX_ITERATIONS = 10


def _parse_diagnosis(text: str) -> Diagnosis | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return Diagnosis(**json.loads(match.group(0)))
    except (ValueError, TypeError):
        return None


def _assistant_message(content: str, calls: list[dict[str, Any]]) -> dict[str, Any]:
    tool_calls = [
        {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
        for c in calls
    ]
    return {"role": "assistant", "content": content or None, "tool_calls": tool_calls}


def investigate(symptom: str, llm: Any, ledger: EvidenceLedger, events: EventLog) -> tuple[Diagnosis, list[dict[str, Any]]]:
    """Plain tool-calling loop. Returns the enforced Diagnosis and the tool calls made."""
    load_all()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Incident report: {symptom}"},
    ]
    specs = REGISTRY.openai_specs()
    made: list[dict[str, Any]] = []
    diagnosis: Diagnosis | None = None
    for step in range(MAX_ITERATIONS):
        last_step = step == MAX_ITERATIONS - 1
        if last_step:
            messages.append({"role": "user", "content": FINAL_REMINDER})
        response = llm.chat(messages, tools=None if last_step else specs)
        events.emit("agent_step", {"step": step, "content": response.content, "tool_calls": response.tool_calls})
        if not response.tool_calls:
            diagnosis = _parse_diagnosis(response.content)
            if diagnosis:
                break
            messages += [{"role": "assistant", "content": response.content}, {"role": "user", "content": FINAL_REMINDER}]
            continue
        messages.append(_assistant_message(response.content, response.tool_calls))
        for call in response.tool_calls:
            events.emit("tool_call", {"name": call["name"], "args": call["arguments"]})
            result = REGISTRY.call(call["name"], call["arguments"], ledger)
            events.emit("tool_result", {"name": call["name"], "result": result})
            made.append({
                "tool": call["name"],
                "args": call["arguments"],
                "ok": not result.startswith("Error"),
                "evidence": re.findall(r"E-\d+", result),
            })
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    if diagnosis is None:
        diagnosis = Diagnosis(summary="Agent did not produce a valid diagnosis", next_steps=["Escalate to a human"])
        events.emit("error", {"reason": "no valid diagnosis"})
    final = ledger.enforce(diagnosis)
    events.emit("diagnosis", final.to_dict())
    return final, made


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
