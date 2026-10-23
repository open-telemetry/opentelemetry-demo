"""A thin, provider-agnostic LLM adapter with tool calling.

The agent loop talks only to this module, using three neutral message shapes:
    {"role": "user", "content": "text"}
    {"role": "assistant", "content": "text", "tool_calls": [ToolCall, ...]}
    {"role": "tool", "tool_call_id": "...", "content": "tool result as text"}
Each provider class below converts those to its own SDK format and back.

Settings come from .env.incident (explicit path, never the demo's .env):
    LLM_PROVIDER  anthropic | openai     LLM_MODEL    model name
    LLM_API_KEY   the key                LLM_BASE_URL optional, OpenAI-compatible servers

Run `python -m oncall.llm --check` to test a plain completion and a tool-call round trip.
"""
import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parent.parent / ".env.incident"
TIMEOUT_SECONDS = 60


class LLMNotConfigured(Exception):
    """Settings or SDK missing. The message says what to fix."""


class LLMError(Exception):
    """The provider answered with something we cannot use."""


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema for the arguments


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)  # {"input_tokens": int, "output_tokens": int}; cache reads count as input

    def as_message(self) -> dict:
        """The reply in neutral form, ready to append to the message list."""
        return {"role": "assistant", "content": self.text, "tool_calls": self.tool_calls}


class AnthropicProvider:
    def __init__(self, api_key: str, model: str, base_url: str | None):
        try:
            import anthropic
        except ImportError:
            raise LLMNotConfigured("LLM_PROVIDER=anthropic but the SDK is missing: pip install anthropic")
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url, timeout=TIMEOUT_SECONDS)
        self.model = model

    def complete(self, system: str, messages: list[dict], tools: list[ToolSpec], max_tokens: int) -> Reply:
        wire = []
        for m in messages:
            if m["role"] == "user":
                wire.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                blocks = [{"type": "text", "text": m["content"]}] if m["content"] else []
                blocks += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                           for c in m.get("tool_calls", [])]
                wire.append({"role": "assistant", "content": blocks})
            else:  # a tool result; Anthropic wants results from one turn together in one user message
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                if wire and wire[-1]["role"] == "user" and isinstance(wire[-1]["content"], list):
                    wire[-1]["content"].append(block)
                else:
                    wire.append({"role": "user", "content": [block]})

        # Prompt caching: mark the end of the system prompt and of the tool list, so those two
        # stable blocks are re-read cheaply on later calls (ignored by the API if they are too short).
        cache = {"type": "ephemeral"}
        kwargs = {"model": self.model, "max_tokens": max_tokens, "messages": wire}
        if system:
            kwargs["system"] = [{"type": "text", "text": system, "cache_control": cache}]
        if tools:
            kwargs["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters}
                               for t in tools]
            kwargs["tools"][-1]["cache_control"] = cache
        response = self.client.messages.create(**kwargs)

        text = "".join(b.text for b in response.content if b.type == "text")
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in response.content if b.type == "tool_use"]
        u = response.usage
        input_tokens = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0) \
            + (getattr(u, "cache_read_input_tokens", 0) or 0)
        return Reply(text, calls, {"input_tokens": input_tokens, "output_tokens": u.output_tokens or 0})


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, base_url: str | None):
        try:
            import openai
        except ImportError:
            raise LLMNotConfigured("LLM_PROVIDER=openai but the SDK is missing: pip install openai")
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=TIMEOUT_SECONDS)
        self.model = model

    def complete(self, system: str, messages: list[dict], tools: list[ToolSpec], max_tokens: int) -> Reply:
        # max_tokens is not sent: newer OpenAI models reject that name and want another one.
        wire = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "assistant":
                entry = {"role": "assistant", "content": m["content"] or None}
                if m.get("tool_calls"):
                    entry["tool_calls"] = [
                        {"id": c.id, "type": "function",
                         "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                        for c in m["tool_calls"]]
                wire.append(entry)
            else:  # "user" and "tool" messages are already in OpenAI's shape
                wire.append(m)

        kwargs = {"model": self.model, "messages": wire}
        if tools:
            kwargs["tools"] = [{"type": "function",
                                "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                               for t in tools]
        response = self.client.chat.completions.create(**kwargs)

        message = response.choices[0].message
        calls = []
        for c in message.tool_calls or []:
            try:
                arguments = json.loads(c.function.arguments or "{}")
            except ValueError:
                raise LLMError(f"tool call {c.function.name!r} had arguments that are not JSON")
            calls.append(ToolCall(c.id, c.function.name, arguments))
        usage = {}
        if response.usage:
            usage = {"input_tokens": response.usage.prompt_tokens or 0, "output_tokens": response.usage.completion_tokens or 0}
        return Reply(message.content or "", calls, usage)


PROVIDERS = {"anthropic": AnthropicProvider, "openai": OpenAIProvider}


class LLM:
    def __init__(self, provider, api_key: str):
        self.provider = provider
        self.api_key = api_key  # kept only so error messages can be scrubbed of it

    def complete(self, system: str, messages: list[dict], tools: list[ToolSpec] | None = None,
                 max_tokens: int = 1024) -> Reply:
        return self.provider.complete(system, messages, tools or [], max_tokens)


def make_llm(settings: dict[str, str] | None = None) -> LLM:
    """Build the LLM from .env.incident. Raises LLMNotConfigured with a clear message."""
    if settings is None:
        settings = {k: v for k, v in dotenv_values(ENV_FILE).items() if v} if ENV_FILE.exists() else {}
    missing = [k for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY") if k not in settings]
    if missing:
        raise LLMNotConfigured(f"no key configured: {', '.join(missing)} not set in .env.incident")
    name = settings["LLM_PROVIDER"].lower()
    if name not in PROVIDERS:
        raise LLMNotConfigured(f"unknown LLM_PROVIDER {name!r}; supported: {', '.join(PROVIDERS)}")
    provider = PROVIDERS[name](settings["LLM_API_KEY"], settings["LLM_MODEL"], settings.get("LLM_BASE_URL"))
    return LLM(provider, settings["LLM_API_KEY"])


# ---------------------------------------------------------------------------
# `python -m oncall.llm --check`
# ---------------------------------------------------------------------------

ADD_TOOL = ToolSpec(
    name="add",
    description="Add two integers and return the sum.",
    parameters={"type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"]},
)


def _scrub(llm: LLM, text: str) -> str:
    """Make sure an SDK error message can never print the key."""
    return text.replace(llm.api_key, "<key>")[:300]


def check_completion(llm: LLM) -> str:
    """One tiny completion. Returns a detail string; raises on failure."""
    reply = llm.complete("", [{"role": "user", "content": "Reply with the single word: ready"}], max_tokens=20)
    if not reply.text.strip():
        raise LLMError("the reply was empty")
    return f"model said {reply.text.strip()[:40]!r}"


def check_tool_round_trip(llm: LLM) -> str:
    """Ask for a tool call, send back a result, expect a final text answer."""
    messages = [{"role": "user", "content": "Use the add tool to add 2 and 3, then tell me the result."}]
    first = llm.complete("", messages, tools=[ADD_TOOL], max_tokens=200)
    if len(first.tool_calls) != 1 or first.tool_calls[0].name != "add":
        raise LLMError(f"expected one call to 'add', got {[c.name for c in first.tool_calls]}")
    call = first.tool_calls[0]
    if not all(isinstance(call.arguments.get(k), int) for k in ("a", "b")):
        raise LLMError(f"arguments were not two integers: {call.arguments}")

    messages += [first.as_message(), {"role": "tool", "tool_call_id": call.id, "content": "5"}]
    second = llm.complete("", messages, tools=[ADD_TOOL], max_tokens=200)
    if not second.text.strip():
        raise LLMError("no final text after the tool result")
    return f"called add({call.arguments}), final answer {second.text.strip()[:40]!r}"


def run_check() -> int:
    try:
        llm = make_llm()
    except LLMNotConfigured as exc:
        print(f"FAIL  {'tiny completion':22}: {exc}")
        print(f"FAIL  {'tool-call round trip':22}: not run")
        return 1

    failed = False
    for label, check in (("tiny completion", check_completion), ("tool-call round trip", check_tool_round_trip)):
        try:
            print(f"PASS  {label:22}: {check(llm)}")
        except Exception as exc:  # any SDK or network error becomes one FAIL line, not a traceback
            failed = True
            print(f"FAIL  {label:22}: {type(exc).__name__}: {_scrub(llm, str(exc))}")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM adapter checks")
    parser.add_argument("--check", action="store_true", help="test a completion and a tool-call round trip")
    args = parser.parse_args()
    if not args.check:
        parser.error("nothing to do; use --check")
    sys.exit(run_check())
