"""Investigation loop: the LLM picks tools one at a time until it can summarise."""

import json
import re

from oncall.agent.confidence import assess
from oncall.agent.diagnosis import diagnose, escalate_unknown
from oncall.agent.evidence import validate
from oncall.agent.llm import LLM, LLMError
from oncall.agent.prompts import INVESTIGATE, SYSTEM
from oncall.agent.runlog import RunLog
from oncall.config import load_settings
from oncall.models import Alert, Diagnosis, ToolResult, llm_view, make_error
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
FORCE_FINISH = (
    "Stop investigating now. Call finish with a symptom summary that cites the "
    "evidence ids collected so far and says what is still unknown."
)
KEEP_FULL_RESULTS = 2
COMPACT_SUMMARY_CHARS = 200
COMPACT_MAX_IDS = 5
FALLBACK_EVIDENCE = 5
FALLBACK_FINDING_CHARS = 150
REQUEST_TOO_LARGE = 413
# Groq's 413 text, e.g. "Limit 8000, Requested 9512"; captures both numbers.
LIMIT_REQUESTED = re.compile(r"Limit (\d+), Requested (\d+)")
SHRINK_MARGIN_TOKENS = 300


def estimate_tokens(messages: list[dict], tools: list[dict]) -> int:
    """Rough prompt size in tokens: characters of the JSON request / 4."""
    return (len(json.dumps(messages, ensure_ascii=False)) + len(json.dumps(tools))) // 4


def _compact_content(content: str, level: int) -> str:
    """Shrink one tool message. Level 1: summary + ids; 2: truncated; 3: omitted."""
    data = json.loads(content)
    if level >= 3:
        return json.dumps({"tool": data.get("tool"), "omitted": "see run log"})
    ids = data.get("evidence_ids") or [e["id"] for e in data.get("evidence", [])]
    summary = data.get("summary", "")
    if level >= 2:
        summary, ids = summary[:COMPACT_SUMMARY_CHARS], ids[:COMPACT_MAX_IDS]
    compact = {"tool": data.get("tool"), "summary": summary, "evidence_ids": ids}
    if data.get("error"):
        compact["error"] = data["error"]
    return json.dumps(compact, ensure_ascii=False)


def compact(messages: list[dict], keep_full: int, level: int = 1) -> None:
    """Compact every tool message except the last `keep_full`, in place."""
    indexes = [i for i, m in enumerate(messages) if m["role"] == "tool"]
    targets = indexes[:-keep_full] if keep_full else indexes
    for i in targets:
        messages[i] = {
            **messages[i],
            "content": _compact_content(messages[i]["content"], level),
        }


def fit_budget(messages: list[dict], tools: list[dict], budget: int) -> int:
    """Compact until the prompt fits `budget` tokens (or nothing is left to cut).

    Returns the final estimate; the caller stops if it is still over budget.
    """
    compact(messages, KEEP_FULL_RESULTS)
    for keep_full, level in ((0, 1), (0, 2), (1, 3)):
        if estimate_tokens(messages, tools) <= budget:
            break
        compact(messages, keep_full, level)
    return estimate_tokens(messages, tools)


def fallback_summary(runlog: RunLog, reason: str) -> str:
    """Deterministic summary from the run log, for when the LLM gives none."""
    results = [e["result"] for e in runlog.events("tool_result")]
    called = ", ".join(r["tool"] for r in results) or "none"
    parts = [
        f"Investigation stopped ({reason}) before a summary. Tools called: {called}."
    ]
    findings = [
        f"{r['tool']}: {r['summary'][:FALLBACK_FINDING_CHARS]}"
        for r in results
        if r.get("ok") and r.get("summary")
    ]
    if findings:
        parts.append("Findings: " + " | ".join(findings[-FALLBACK_EVIDENCE:]))
    evidence = list(runlog.evidence_index().values())[:FALLBACK_EVIDENCE]
    if evidence:
        parts.append(
            "Key evidence: "
            + "; ".join(f"[{e['id']}] {e.get('text', '')[:120]}" for e in evidence)
        )
    else:
        parts.append("No evidence was collected.")
    return " ".join(parts)


def shrunk_budget(budget: int, error: LLMError) -> int:
    """A smaller prompt budget after a 413: cut by the provider's overshoot, else by 1/3."""
    match = LIMIT_REQUESTED.search(error.body or str(error))
    if match:
        over = int(match.group(2)) - int(match.group(1))
        return max(budget - over - SHRINK_MARGIN_TOKENS, 0)
    return budget * 2 // 3


def chat_within_budget(
    llm: LLM, messages: list[dict], tools: list[dict], budget: int, runlog: RunLog
):
    """llm.chat(); on HTTP 413 compact to a smaller budget and retry once.

    Returns (reply, budget) so later calls keep the smaller budget.
    """
    try:
        return llm.chat(messages, tools), budget
    except LLMError as exc:
        if exc.status != REQUEST_TOO_LARGE:
            raise
        smaller = shrunk_budget(budget, exc)
        runlog.log("budget", reason="413", budget=budget, new_budget=smaller)
        fit_budget(messages, tools, smaller)
        return llm.chat(messages, tools), smaller


def _forced_finish(llm: LLM, messages: list[dict], runlog: RunLog, budget: int) -> str:
    """One last call with only `finish` available. Returns "" if it fails."""
    final = [*messages, {"role": "user", "content": FORCE_FINISH}]
    fit_budget(final, [FINISH_SCHEMA], budget)
    try:
        reply, _ = chat_within_budget(llm, final, [FINISH_SCHEMA], budget, runlog)
    except LLMError as exc:
        runlog.log("error", where="forced_finish", error=str(exc))
        return ""
    runlog.log(
        "llm_call",
        step="forced_finish",
        model=reply.model,
        usage=reply.usage,
        tool_calls=reply.tool_calls,
    )
    for call in reply.tool_calls:
        if call["name"] == FINISH and call["args"]:
            summary = str(call["args"].get("summary", "")).strip()
            if summary:
                return summary
    return ""


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
    budget = settings.LLM_MAX_PROMPT_TOKENS
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

    def stop_with_error(reason: str) -> dict:
        nonlocal stopped, summary
        stopped, summary = "error", f"{reason}. {fallback_summary(runlog, 'error')}"
        return done()

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
        return stop_with_error(f"LLM unavailable: {exc}")

    reason = "max_steps"
    while steps < max_steps:
        tokens = fit_budget(messages, tool_schemas, budget)
        if tokens > budget:
            runlog.log("budget", step=steps, tokens=tokens, budget=budget)
            reason = "token budget"
            break
        steps += 1
        try:
            reply, budget = chat_within_budget(
                llm, messages, tool_schemas, budget, runlog
            )
        except LLMError as exc:
            runlog.log("error", where="llm_call", step=steps, error=str(exc))
            return stop_with_error(f"LLM call failed: {exc}")
        runlog.log(
            "llm_call",
            step=steps,
            model=reply.model,
            usage=reply.usage,
            text=reply.text,
            tool_calls=reply.tool_calls,
        )

        if not reply.tool_calls:
            text_only_replies += 1
            if text_only_replies >= 2:
                return stop_with_error(f"no tool call; model said: {reply.text[:300]}")
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
                    "content": json.dumps(llm_view(result), ensure_ascii=False),
                }
            )
            errors_in_a_row = 0 if result["ok"] else errors_in_a_row + 1
            if errors_in_a_row >= MAX_CONSECUTIVE_ERRORS:
                return stop_with_error(
                    f"stopped after {errors_in_a_row} tool errors in a row"
                )

    summary = _forced_finish(llm, messages, runlog, budget) or fallback_summary(
        runlog, reason
    )
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
    result["diagnosis"] = finalise(diagnose(runlog, alert, llm), runlog)
    return result


def finalise(d: Diagnosis, runlog: RunLog) -> Diagnosis:
    """Validate the evidence (F13), then set confidence and decision (F15)."""
    d, problems = validate(d, runlog)
    runlog.log("decision", stage="validated", diagnosis=d, problems=problems)
    d = assess(d, runlog)
    runlog.log("decision", stage="assessed", diagnosis=d)
    return d
