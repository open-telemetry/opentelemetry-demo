"""Investigation loop: the LLM picks tools one at a time until it can summarise."""

import json

from oncall.agent.diagnosis import diagnose, escalate_unknown
from oncall.agent.llm import LLM, LLMError
from oncall.agent.prompts import INVESTIGATE, SYSTEM
from oncall.agent.runlog import RunLog
from oncall.config import load_settings
from oncall.models import Alert, ToolResult, make_error
from oncall.tools import TOOL_SCHEMAS, TOOLS

FINISH = "finish"
FINISH_SCHEMA = {
    "name": FINISH,
    "description": "End the investigation with a symptom summary citing evidence ids.",
    "input_schema": {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    },
}
MAX_CONSECUTIVE_ERRORS = 2
NUDGE = "Call a tool to continue the investigation, or call finish."


def _run_tool(tools: dict, call: dict) -> ToolResult:
    name, args = call["name"], call["args"]
    if name not in tools:
        known = ", ".join(sorted([*tools, FINISH]))
        return make_error(name, args or {}, f"unknown tool {name!r}; known: {known}")
    if args is None:
        return make_error(name, {}, call.get("error", "missing arguments"))
    try:
        return tools[name](**args)
    except Exception as exc:  # noqa: BLE001
        return make_error(name, args, f"{type(exc).__name__}: {exc}")


def investigate(
    alert: Alert,
    tools: dict = TOOLS,
    llm: LLM | None = None,
    max_steps: int | None = None,
    runlog: RunLog | None = None,
    schemas: dict | None = None,
) -> dict:
    """Investigate an alert. Returns run_id, summary, steps, tools_used and stopped."""
    settings = load_settings()
    max_steps = max_steps or settings.MAX_STEPS
    runlog = runlog or RunLog(runs_dir=settings.RUNS_DIR)
    schemas = TOOL_SCHEMAS if schemas is None else schemas
    tool_schemas = [schemas[n] for n in tools if n in schemas] + [FINISH_SCHEMA]
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": INVESTIGATE.format(**alert)},
    ]
    runlog.log("alert", alert=alert)

    tools_used: list[str] = []
    summary, stopped, steps = "", "max_steps", 0
    errors_in_a_row = 0
    text_only_replies = 0

    def done() -> dict:
        runlog.log("finish", stopped=stopped, summary=summary, steps=steps)
        return {
            "run_id": runlog.run_id,
            "summary": summary,
            "steps": steps,
            "tools_used": tools_used,
            "stopped": stopped,
        }

    try:
        if llm is None:
            llm = LLM(settings)
    except LLMError as exc:
        runlog.log("error", where="llm_init", error=str(exc))
        stopped, summary = "error", f"LLM unavailable: {exc}"
        return done()

    while steps < max_steps:
        steps += 1
        try:
            reply = llm.chat(messages, tool_schemas)
        except LLMError as exc:
            runlog.log("error", where="llm_call", step=steps, error=str(exc))
            stopped, summary = "error", f"LLM call failed: {exc}"
            return done()
        runlog.log(
            "llm_call",
            step=steps,
            usage=reply.usage,
            text=reply.text,
            tool_calls=reply.tool_calls,
        )

        if not reply.tool_calls:
            text_only_replies += 1
            if text_only_replies >= 2:
                stopped, summary = "error", reply.text
                return done()
            messages += [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": NUDGE},
            ]
            continue

        messages.append(
            {
                "role": "assistant",
                "content": reply.text or None,
                "tool_calls": [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {
                            "name": c["name"],
                            "arguments": json.dumps(c["args"] or {}),
                        },
                    }
                    for c in reply.tool_calls
                ],
            }
        )
        for call in reply.tool_calls:
            if call["name"] == FINISH and call["args"] is not None:
                stopped = "finish"
                summary = str(call["args"].get("summary", ""))
                return done()
            runlog.log("tool_call", step=steps, name=call["name"], args=call["args"])
            result = _run_tool(tools, call)
            runlog.log("tool_result", step=steps, name=call["name"], result=result)
            tools_used.append(call["name"])
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": call["name"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
            errors_in_a_row = 0 if result["ok"] else errors_in_a_row + 1
            if errors_in_a_row >= MAX_CONSECUTIVE_ERRORS:
                stopped = "error"
                summary = f"stopped after {errors_in_a_row} tool errors in a row"
                return done()

    return done()


def investigate_and_diagnose(
    alert: Alert,
    tools: dict = TOOLS,
    llm: LLM | None = None,
    max_steps: int | None = None,
    runlog: RunLog | None = None,
    schemas: dict | None = None,
) -> dict:
    """Investigate, then diagnose. Returns investigate()'s dict plus "diagnosis"."""
    settings = load_settings()
    runlog = runlog or RunLog(runs_dir=settings.RUNS_DIR)
    if llm is None:
        try:
            llm = LLM(settings)
        except LLMError as exc:
            result = investigate(alert, tools, None, max_steps, runlog, schemas)
            result["diagnosis"] = escalate_unknown(f"LLM unavailable: {exc}")
            runlog.log("decision", diagnosis=result["diagnosis"], valid=False)
            return result
    result = investigate(alert, tools, llm, max_steps, runlog, schemas)
    result["diagnosis"] = diagnose(runlog, alert, llm)
    return result
