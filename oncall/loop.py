"""A plain tool-calling investigation loop.

The model sees only the symptom text and the tool list. Each turn it picks a tool, the loop runs it,
stores the full sanitised result in the ledger and shows the model a compact view of it
(see toolbox.py). It ends by calling submit_diagnosis, whose arguments become the candidate.

Budgets (LoopConfig): tool calls, total tokens (input + output) and tokens per reply. When a budget
runs out, or the model repeats an identical call, the loop stops investigating and asks once more for
a diagnosis from what was found. If no valid answer ever arrives, the candidate is an explicit
"unknown" with confidence 0 and the reason in `limitations`; the loop never invents a diagnosis.
Validation against the ledger is NOT done here.
"""
import json
import secrets
from dataclasses import dataclass, field

from oncall import toolbox
from oncall.llm import ToolSpec
from oncall.prompts import DEFAULT_SYMPTOM, system_prompt
from tools.ledger import Ledger
from tools.result import iso, utc_now

SUBMIT = "submit_diagnosis"
EVIDENCE_KINDS = ("trace", "log", "metric", "container")
CHARS_PER_TOKEN = 3  # rough, only used to project the next call's size
MAX_WRAPUP_TRIES = 2
MAX_MALFORMED = 2


@dataclass
class LoopConfig:
    token_budget: int = 60000  # input + output tokens over the whole run
    step_budget: int = 10  # tool calls, valid or not
    max_tokens: int = 1200  # per model reply


def _string(description: str) -> dict:
    return {"type": "string", "description": description}


SUBMIT_SPEC = ToolSpec(
    name=SUBMIT,
    description="Finish the investigation with your diagnosis. Call this exactly once, when you are done.",
    parameters={
        "type": "object",
        "properties": {
            "component": _string("Service or container judged to be the root cause, or 'unknown'."),
            "cause": _string("What is wrong and why, in 1-3 sentences."),
            "stated_confidence": {"type": "number", "minimum": 0, "maximum": 1,
                                  "description": "Your own probability from 0 to 1 that component is right."},
            "evidence": {"type": "array", "items": {"type": "object", "properties": {
                "ledger_id": _string("The id of the tool result, e.g. T3."),
                "kind": {"type": "string", "enum": list(EVIDENCE_KINDS)},
                "claim": _string("What this item shows, one sentence."),
                "quote": _string("Text copied EXACTLY from that result: a trace ID, a log message, a container name or a number as printed."),
                "value": _string("Optional second exact string from the same result, e.g. 'exited'."),
            }, "required": ["ledger_id", "kind", "claim", "quote"]}},
            "alternatives_considered": {"type": "array", "items": {"type": "object", "properties": {
                "hypothesis": _string("An explanation you considered."),
                "why_rejected": _string("Why the evidence argues against it."),
            }, "required": ["hypothesis", "why_rejected"]}},
            "limitations": {"type": "array", "items": {"type": "string"},
                            "description": "What you could not check or could not rely on."},
        },
        "required": ["component", "cause", "stated_confidence", "evidence"],
    },
)


class DiagnosisError(Exception):
    """submit_diagnosis arguments are not in the expected shape. The message goes back to the model."""


def _is_text(value) -> bool:
    return isinstance(value, str)


def _text_list(value, field_name: str, item_keys: tuple[str, ...]) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(i, dict) for i in value):
        raise DiagnosisError(f"{field_name} must be a list of objects")
    for item in value:
        for key in item_keys:
            if not _is_text(item.get(key)) or not item[key]:
                raise DiagnosisError(f"every {field_name} item needs a non-empty text {key!r}")
    return value


def parse_submission(args: dict) -> dict:
    """Check the shape of a submit_diagnosis call. Strings are kept exactly as sent (quotes are never trimmed)."""
    if not isinstance(args, dict):
        raise DiagnosisError("arguments must be a JSON object")
    for key in ("component", "cause"):
        if not _is_text(args.get(key)) or not args[key].strip():
            raise DiagnosisError(f"{key!r} must be non-empty text")
    confidence = args.get("stated_confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise DiagnosisError("'stated_confidence' must be a number from 0 to 1")

    evidence = _text_list(args.get("evidence"), "evidence", ("ledger_id", "kind", "claim", "quote"))
    for item in evidence:
        if item["kind"] not in EVIDENCE_KINDS:
            raise DiagnosisError(f"evidence kind must be one of {list(EVIDENCE_KINDS)}")
        if item.get("value") is not None and not _is_text(item["value"]):
            raise DiagnosisError("evidence 'value' must be text when given")
    alternatives = _text_list(args.get("alternatives_considered"), "alternatives_considered", ("hypothesis", "why_rejected"))
    limitations = args.get("limitations") or []
    if not isinstance(limitations, list) or not all(_is_text(i) for i in limitations):
        raise DiagnosisError("'limitations' must be a list of text")

    return {
        "component": args["component"],
        "cause": args["cause"],
        "stated_confidence": float(confidence),
        "evidence": [{"ledger_id": e["ledger_id"], "kind": e["kind"], "claim": e["claim"], "quote": e["quote"],
                      "value": e.get("value")} for e in evidence],
        "alternatives_considered": [{"hypothesis": a["hypothesis"], "why_rejected": a["why_rejected"]} for a in alternatives],
        "limitations": list(limitations),
    }


@dataclass
class RunResult:
    candidate: dict
    run_info: dict
    ledger: Ledger
    steps: list[dict] = field(default_factory=list)


STOP_TEXT = {
    "step_budget": "the tool-call budget was used up",
    "token_budget": "the token budget was used up",
    "repeated_call": "the model repeated an identical tool call",
}


class _Investigation:
    def __init__(self, llm, symptom: str, config: LoopConfig, tools: dict):
        self.llm, self.symptom, self.config, self.tools = llm, symptom, config, tools
        self.ledger = Ledger()
        self.system = system_prompt(config.step_budget)
        self.specs = [t.spec() for t in tools.values()] + [SUBMIT_SPEC]
        self.messages = [{"role": "user", "content": f"Symptom report: {symptom}"}]
        self.steps: list[dict] = []
        self.seen: dict[tuple, str] = {}  # (tool, arguments) -> ledger id, to catch identical repeats
        self.tokens_in = self.tokens_out = 0
        self.last_in = self._estimate_tokens()
        self.last_out = 0
        self.added_chars = 0  # characters added since the last model call
        self.wrapup = False  # True once only a diagnosis may be given
        self.wrapup_noted = False
        self.wrapup_tries = 0
        self.stop_reason: str | None = None
        self.llm_error: str | None = None
        self.malformed = 0
        self.nudges = 0
        self.candidate: dict | None = None
        self.done = False

    # --- token budget -------------------------------------------------------------------

    def _estimate_tokens(self) -> int:
        chars = len(self.system) + len(json.dumps([s.parameters for s in self.specs]))
        chars += sum(len(str(m.get("content", ""))) for m in self.messages)
        return chars // CHARS_PER_TOKEN

    def _can_afford(self, extra_calls: int) -> bool:
        """Would this call, plus `extra_calls` more of the same size, still fit in the budget?"""
        next_input = self.last_in + self.last_out + self.added_chars // CHARS_PER_TOKEN
        cost = next_input + self.config.max_tokens
        return self.tokens_in + self.tokens_out + cost * (1 + extra_calls) <= self.config.token_budget

    # --- messages -----------------------------------------------------------------------

    def _tool_message(self, call, text: str) -> None:
        self.messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
        self.added_chars += len(text)

    def _note(self, text: str) -> None:
        """Add text for the model after the latest tool result (or as a user message if there is none)."""
        last = self.messages[-1]
        if last["role"] in ("tool", "user") and isinstance(last["content"], str):
            last["content"] += "\n" + text
        else:
            self.messages.append({"role": "user", "content": text})
        self.added_chars += len(text)

    def _start_wrapup(self, reason: str) -> None:
        if not self.wrapup:
            self.wrapup, self.stop_reason = True, reason

    # --- main loop ----------------------------------------------------------------------

    def run(self) -> None:
        while not self.done:
            if not self.wrapup:
                if len(self.steps) >= self.config.step_budget:
                    self._start_wrapup("step_budget")
                elif not self._can_afford(extra_calls=1):  # keep room for the final answer
                    self._start_wrapup("token_budget")
            if self.wrapup:
                if self.wrapup_tries >= MAX_WRAPUP_TRIES:
                    self.llm_error = self.llm_error or "the model did not submit a diagnosis when asked to conclude"
                    break
                if not self._can_afford(extra_calls=0):
                    break  # no budget left even to ask for the answer
                if not self.wrapup_noted:
                    self.wrapup_noted = True
                    self._note("Stop investigating. Do not call any other tool. Call submit_diagnosis now with what you have; "
                               "use component 'unknown' and a low stated_confidence if the evidence is not enough.")
                self.wrapup_tries += 1
            reply = self._ask()
            if reply is None:
                break
            self._handle(reply)

    def _ask(self):
        try:
            reply = self.llm.complete(self.system, self.messages, self.specs, self.config.max_tokens)
        except Exception as exc:  # timeouts, rate limits, bad requests: all end the run with a recorded error
            key = getattr(self.llm, "api_key", "")
            message = str(exc).replace(key, "<key>") if key else str(exc)
            self.llm_error = f"{type(exc).__name__}: {message[:200]}"
            self.stop_reason = "llm_error"
            return None
        usage = reply.usage or {}
        self.last_in = usage.get("input_tokens") or self._estimate_tokens()
        self.last_out = usage.get("output_tokens") or len(reply.text) // CHARS_PER_TOKEN + 30 * len(reply.tool_calls)
        self.tokens_in += self.last_in
        self.tokens_out += self.last_out
        self.added_chars = 0
        return reply

    def _handle(self, reply) -> None:
        if not reply.text and not reply.tool_calls:
            reply.text = "(empty reply)"  # providers reject an empty assistant message
        self.messages.append(reply.as_message())
        if not reply.tool_calls:
            self.nudges += 1
            if self.nudges >= 2:
                self.llm_error = self.llm_error or "the model stopped without calling submit_diagnosis"
                self.stop_reason = self.stop_reason or "no_submission"
                self.done = True
            else:
                self._note(f"Continue with a tool call, or call {SUBMIT} to finish. Do not answer in plain text.")
            return
        submit = next((c for c in reply.tool_calls if c.name == SUBMIT), None)
        if submit:
            for call in reply.tool_calls:
                if call is not submit:
                    self._tool_message(call, f"not run: {SUBMIT} was called in the same turn")
            self._handle_submit(submit)
            return
        for call in reply.tool_calls:
            self._handle_tool(call, reply.text.strip()[:200])

    def _handle_submit(self, call) -> None:
        try:
            self.candidate = parse_submission(call.arguments)
        except DiagnosisError as exc:
            self.malformed += 1
            self._tool_message(call, f"rejected: {exc}. Call {SUBMIT} again with corrected arguments.")
            if self.malformed >= MAX_MALFORMED:
                self.llm_error = f"{SUBMIT} was malformed twice: {exc}"
                self.stop_reason = self.stop_reason or "malformed_submission"
                self.done = True
            return
        self._tool_message(call, "accepted")
        self.done = True

    def _handle_tool(self, call, why: str) -> None:
        if self.wrapup or len(self.steps) >= self.config.step_budget:
            self._tool_message(call, f"not run: the budget is used up. Call {SUBMIT} now.")
            return
        step = {"tool": call.name, "arguments": call.arguments, "finding": "", "ledger_id": None, "why": why}
        self.steps.append(step)

        tool = self.tools.get(call.name)
        if tool is None:
            self.llm_error = self.llm_error or f"the model called an unknown tool {call.name!r}"
            step["finding"] = "unknown tool; not run"
            self._tool_message(call, f"unknown tool {call.name!r}. Available: {', '.join(self.tools)}, {SUBMIT}.")
            return
        try:
            arguments = toolbox.validate_arguments(tool, call.arguments)
            step["arguments"] = arguments
            key = (call.name, json.dumps(arguments, sort_keys=True))
            if key in self.seen:
                step["finding"] = f"repeat of {self.seen[key]}; not run"
                self._tool_message(call, f"This exact call was already made as {self.seen[key]}. Repeating it adds nothing.")
                self._start_wrapup("repeated_call")
                return
            result = toolbox.call_tool(tool, arguments)
        except toolbox.ArgumentError as exc:
            step["finding"] = f"rejected arguments: {exc}"[:150]
            self._tool_message(call, f"error: {exc}. Fix the arguments and try again.")
            return

        entry = self.ledger.add(call.name, arguments, result)
        view = toolbox.compact_view(entry)
        self.seen[key] = entry.id
        step["ledger_id"] = entry.id
        step["finding"] = toolbox.finding_line(view, call.name)
        self._tool_message(call, toolbox.view_text(view))

    # --- result -------------------------------------------------------------------------

    def _limitations(self) -> list[str]:
        notes = []
        if self.stop_reason in STOP_TEXT:
            notes.append(f"Investigation was cut short: {STOP_TEXT[self.stop_reason]}.")
        if self.llm_error:
            notes.append(f"Run problem: {self.llm_error}")
        for entry in self.ledger.list():
            if entry.result["state"] == "backend_error":
                notes.append(f"{entry.id} ({entry.tool}) returned backend_error: {entry.result.get('error')}. Its evidence is missing.")
        return notes

    def result(self, started) -> RunResult:
        notes = self._limitations()
        if self.candidate is None:
            reason = self.llm_error or STOP_TEXT.get(self.stop_reason or "", "the run ended without an answer")
            candidate = {
                "component": "unknown",
                "cause": f"No diagnosis was produced: {reason}. See investigation_steps and the ledger for what the tools showed.",
                "stated_confidence": 0.0, "evidence": [], "alternatives_considered": [], "limitations": [],
            }
        else:
            candidate = dict(self.candidate)
        candidate["limitations"] = candidate["limitations"] + [n for n in notes if n not in candidate["limitations"]]
        candidate = {
            "component": candidate["component"], "cause": candidate["cause"],
            "stated_confidence": candidate["stated_confidence"], "evidence": candidate["evidence"],
            "alternatives_considered": candidate["alternatives_considered"],
            "investigation_steps": [dict(s) for s in self.steps],
            "limitations": candidate["limitations"],
        }
        run_info = {
            "incident_id": f"inc-{started:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}",
            "started_at": iso(started),
            "trigger": self.symptom,
            "steps_used": len(self.steps),
            "step_budget": self.config.step_budget,
            "budget_exhausted": self.stop_reason in ("step_budget", "token_budget"),
            "llm_error": self.llm_error,
            "tokens_used": self.tokens_in + self.tokens_out,
            "tokens_input": self.tokens_in,
            "tokens_output": self.tokens_out,
            "token_budget": self.config.token_budget,
            "stop_reason": self.stop_reason or ("submitted" if self.candidate else "ended"),
            "model": getattr(getattr(self.llm, "provider", None), "model", None),
        }
        return RunResult(candidate, run_info, self.ledger, self.steps)


def run_investigation(llm, symptom: str = DEFAULT_SYMPTOM, config: LoopConfig | None = None,
                      tools: dict | None = None) -> RunResult:
    """Investigate `symptom` with `llm` (anything with .complete(system, messages, tools, max_tokens) -> Reply)."""
    started = utc_now()
    run = _Investigation(llm, symptom, config or LoopConfig(), tools or toolbox.TOOLS)
    run.run()
    return run.result(started)
