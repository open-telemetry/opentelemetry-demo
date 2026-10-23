"""Provider-neutral LLM wrapper: the one file to change when the model provider changes.

Configuration (environment variables, or bosch-incident-zero/.env which is git-ignored):
  LLM_PROVIDER     anthropic | openai | gemini (Gemini's OpenAI-compatible endpoint)
  LLM_MODEL        model id issued by the organisers (anthropic default: claude-opus-5-5)
  LLM_API_KEY      API key (never commit it)
  LLM_BASE_URL     optional custom endpoint (e.g. an organiser proxy or OpenAI-compatible server)
  LLM_EFFORT       optional Anthropic effort: low | medium | high | xhigh | max
  LLM_MAX_RETRIES  retries on rate limits / 5xx / network errors (default 5)
  LLM_FALLBACKS    anthropic only: 1 (default) enables server-side refusal fallbacks on api.anthropic.com
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from ..config import load_env_file

ANTHROPIC_API_URL = "https://api.anthropic.com"
ANTHROPIC_DEFAULT_MODEL = "claude-opus-5-5"
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-fable-5-1", "claude-sonnet-5-5"}


class LLMError(Exception):
    """The model call failed and should not be retried further."""


class LLMRateLimitError(LLMError):
    """Rate limited even after all retries."""


class LLMConfigError(LLMError):
    """The provider is not configured."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]
    invalid_arguments: Optional[str] = None


@dataclass
class ToolResultMessage:
    call_id: str
    content: str
    is_error: bool = False


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"


@dataclass
class LLMConfig:
    provider: str = "scripted"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    effort: str = ""
    max_tokens: int = 16000
    max_retries: int = 5
    timeout_seconds: float = 180.0
    fallbacks: bool = True

    @classmethod
    def from_env(cls, root_dir: Optional[Path] = None) -> "LLMConfig":
        root = root_dir or Path(__file__).resolve().parents[2]
        file_env = load_env_file(root / ".env")

        def get(key: str, default: str = "") -> str:
            return os.environ.get(key, file_env.get(key, default)).strip()

        provider = get("LLM_PROVIDER", "").lower() or "unset"
        model = get("LLM_MODEL") or (ANTHROPIC_DEFAULT_MODEL if provider == "anthropic" else "")
        return cls(
            provider=provider, model=model, api_key=get("LLM_API_KEY"), base_url=get("LLM_BASE_URL"),
            effort=get("LLM_EFFORT"), max_retries=int(get("LLM_MAX_RETRIES", "5") or 5),
            timeout_seconds=float(get("LLM_TIMEOUT_SECONDS", "180") or 180),
            fallbacks=get("LLM_FALLBACKS", "1") not in ("0", "false", "no"),
        )


def call_with_retries(
    fn: Callable[[], Any],
    classify: Callable[[Exception], Tuple[bool, bool, Optional[float]]],
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Run ``fn`` with exponential backoff. ``classify`` returns (retryable, is_rate_limit, retry_after)."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as e:
            retryable, is_rate_limit, retry_after = classify(e)
            if not retryable:
                cls = LLMRateLimitError if is_rate_limit else LLMError
                raise cls(f"{type(e).__name__}: {str(e)[:300]}") from e
            if attempt >= max_retries:
                cls = LLMRateLimitError if is_rate_limit else LLMError
                raise cls(f"gave up after {attempt + 1} attempts: {type(e).__name__}: {str(e)[:300]}") from e
            delay = retry_after if retry_after is not None else base_delay * (2 ** attempt) + random.uniform(0, 1)
            sleep(min(max(delay, 0.0), max_delay))
            attempt += 1


# A per-day quota will not reset within any useful backoff, so retrying only wastes time.
_DAILY_QUOTA = re.compile(r"PerDay|per day|daily", re.IGNORECASE)


def _is_daily_quota(exc: Exception) -> bool:
    return bool(_DAILY_QUOTA.search(str(exc)))


def _retry_after(exc: Exception) -> Optional[float]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    try:
        value = headers.get("retry-after")
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class LLMSession(ABC):
    """One conversation with the model. History is append-only."""

    @abstractmethod
    def send(self, user_text: Optional[str] = None,
             tool_results: Optional[Sequence[ToolResultMessage]] = None) -> LLMResponse:
        ...


class AnthropicSession(LLMSession):
    def __init__(self, cfg: LLMConfig, system: str, tools: Sequence[Dict[str, Any]]) -> None:
        import anthropic

        self._sdk = anthropic
        self.cfg = cfg
        base_url = cfg.base_url or ANTHROPIC_API_URL
        # Explicit base_url and api_key so ambient ANTHROPIC_* variables from other tools are never used.
        self.client = anthropic.Anthropic(api_key=cfg.api_key or None, base_url=base_url,
                                          max_retries=0, timeout=cfg.timeout_seconds)
        self.system = system
        self.tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                      for t in tools]
        self.messages: List[Dict[str, Any]] = []
        self.use_fallbacks = (cfg.fallbacks and base_url.rstrip("/") == ANTHROPIC_API_URL
                              and cfg.model in _FALLBACK_MODELS)

    def _classify(self, e: Exception) -> Tuple[bool, bool, Optional[float]]:
        sdk = self._sdk
        if isinstance(e, sdk.RateLimitError):
            return not _is_daily_quota(e), True, _retry_after(e)
        if isinstance(e, (sdk.APIConnectionError, sdk.APITimeoutError, sdk.InternalServerError)):
            return True, False, _retry_after(e)
        if isinstance(e, sdk.APIStatusError) and (e.status_code >= 500 or e.status_code in (408, 409, 529)):
            return True, False, _retry_after(e)
        return False, False, None

    def send(self, user_text: Optional[str] = None,
             tool_results: Optional[Sequence[ToolResultMessage]] = None) -> LLMResponse:
        content: List[Dict[str, Any]] = [
            {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
            for r in tool_results or []]
        if user_text:
            content.append({"type": "text", "text": user_text})
        self.messages.append({"role": "user", "content": content})

        kwargs: Dict[str, Any] = {"model": self.cfg.model, "max_tokens": self.cfg.max_tokens,
                                  "system": self.system, "messages": self.messages}
        if self.tools:
            kwargs["tools"] = self.tools
        if self.cfg.effort:
            kwargs["output_config"] = {"effort": self.cfg.effort}
        if self.use_fallbacks:
            kwargs["extra_headers"] = {"anthropic-beta": "server-side-fallback-2026-07-01"}
            kwargs["extra_body"] = {"fallbacks": "default"}

        resp = call_with_retries(lambda: self.client.messages.create(**kwargs), self._classify,
                                 max_retries=self.cfg.max_retries)
        # Append the full content (thinking and tool_use blocks included) so history stays valid.
        self.messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "refusal":
            raise LLMError("model refused the request")
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        calls = [ToolCall(b.id, b.name, dict(b.input or {})) for b in resp.content
                 if getattr(b, "type", "") == "tool_use"]
        return LLMResponse(text=text, tool_calls=calls, stop_reason=resp.stop_reason or "end_turn")


class OpenAISession(LLMSession):
    """OpenAI Chat Completions, or any server exposing that API via LLM_BASE_URL."""

    def __init__(self, cfg: LLMConfig, system: str, tools: Sequence[Dict[str, Any]]) -> None:
        import openai

        self._sdk = openai
        self.cfg = cfg
        self.client = openai.OpenAI(api_key=cfg.api_key or None, base_url=cfg.base_url or None,
                                    max_retries=0, timeout=cfg.timeout_seconds)
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                        "parameters": t["parameters"]}} for t in tools]
        self.messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]

    def _classify(self, e: Exception) -> Tuple[bool, bool, Optional[float]]:
        sdk = self._sdk
        if isinstance(e, sdk.RateLimitError):
            return not _is_daily_quota(e), True, _retry_after(e)
        if isinstance(e, (sdk.APIConnectionError, sdk.APITimeoutError, sdk.InternalServerError)):
            return True, False, _retry_after(e)
        if isinstance(e, sdk.APIStatusError) and e.status_code >= 500:
            return True, False, _retry_after(e)
        return False, False, None

    def send(self, user_text: Optional[str] = None,
             tool_results: Optional[Sequence[ToolResultMessage]] = None) -> LLMResponse:
        for r in tool_results or []:
            self.messages.append({"role": "tool", "tool_call_id": r.call_id, "content": r.content})
        if user_text:
            self.messages.append({"role": "user", "content": user_text})
        kwargs: Dict[str, Any] = {"model": self.cfg.model, "messages": self.messages}
        if self.tools:
            kwargs["tools"] = self.tools
        resp = call_with_retries(lambda: self.client.chat.completions.create(**kwargs), self._classify,
                                 max_retries=self.cfg.max_retries)
        choice = resp.choices[0]
        msg = choice.message
        self.messages.append(msg.model_dump(exclude_none=True))
        calls: List[ToolCall] = []
        for tc in msg.tool_calls or []:
            raw = tc.function.arguments or "{}"
            try:
                args = json.loads(raw)
                calls.append(ToolCall(tc.id, tc.function.name, args if isinstance(args, dict) else {}))
            except ValueError:
                calls.append(ToolCall(tc.id, tc.function.name, {}, invalid_arguments=raw[:200]))
        return LLMResponse(text=msg.content or "", tool_calls=calls, stop_reason=choice.finish_reason or "stop")


ScriptStep = Union[LLMResponse, Callable[[Optional[str], Sequence[ToolResultMessage]], LLMResponse]]


class ScriptedSession(LLMSession):
    """Deterministic stand-in for a model, used by tests and offline dry runs."""

    def __init__(self, steps: Sequence[ScriptStep]) -> None:
        self.steps = list(steps)
        self.received: List[Dict[str, Any]] = []

    def send(self, user_text: Optional[str] = None,
             tool_results: Optional[Sequence[ToolResultMessage]] = None) -> LLMResponse:
        self.received.append({"user_text": user_text, "tool_results": list(tool_results or [])})
        if not self.steps:
            return LLMResponse(text="(script exhausted)")
        step = self.steps.pop(0)
        return step(user_text, list(tool_results or [])) if callable(step) else step


SessionFactory = Callable[[str, Sequence[Dict[str, Any]]], LLMSession]


def session_factory(cfg: Optional[LLMConfig] = None) -> SessionFactory:
    """Return a factory that opens a new session for a system prompt and tool list."""
    cfg = cfg or LLMConfig.from_env()
    if cfg.provider == "anthropic":
        return lambda system, tools: AnthropicSession(cfg, system, tools)
    if cfg.provider in ("openai", "gemini", "openai_compatible"):
        if not cfg.model:
            raise LLMConfigError(f"LLM_MODEL must be set for the {cfg.provider} provider.")
        return lambda system, tools: OpenAISession(cfg, system, tools)
    raise LLMConfigError(
        f"LLM_PROVIDER is '{cfg.provider}'. Set LLM_PROVIDER=anthropic, openai or gemini, plus LLM_API_KEY "
        "(and LLM_MODEL), in the environment or bosch-incident-zero/.env.")
