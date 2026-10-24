"""Provider-neutral LLM wrapper: the one file to change when the model provider changes.

Configuration (environment variables, or bosch-incident-zero/.env which is git-ignored):
  LLM_PROVIDER     anthropic | openai | gemini | openrouter | openai_compatible (needs LLM_BASE_URL).
                   Required: with no provider or no key the factory raises LLMConfigError, there is
                   no offline fallback that produces a diagnosis.
  LLM_MODEL        model id issued by the organisers (anthropic default: claude-opus-5-5)
  LLM_API_KEY      API key (never commit it)
  LLM_BASE_URL     optional custom endpoint (e.g. an organiser proxy, https://openrouter.ai/api/v1)
  LLM_HTTP_REFERER optional HTTP-Referer header (OpenRouter app attribution)
  LLM_APP_TITLE    optional X-Title header (OpenRouter app attribution)
  LLM_MAX_TOKENS   output cap per request (default 16000); lower it when OpenRouter answers 402
  LLM_EFFORT       optional Anthropic effort: low | medium | high | xhigh | max
  LLM_MAX_RETRIES  retries on rate limits / 5xx / network errors (default 5)
  LLM_FALLBACKS    anthropic only: 1 (default) enables server-side refusal fallbacks on api.anthropic.com
  LLM_FALLBACK_MODELS  OpenAI-style providers: comma-separated models tried in order when the current one
                   fails at transport level (402, 404, 408, 429, 5xx, timeout, connection). Bad output
                   never triggers a fallback.
  LLM_FALLBACK_PROVIDER  optional second OpenAI-style provider (e.g. gemini) tried, with its own key, after
                   every model above fails at transport level: LLM_FALLBACK_API_KEY, LLM_FALLBACK_MODELS_2
                   (comma-separated; default gemini-3.5-flash for gemini), LLM_FALLBACK_BASE_URL (optional).

Every LLMResponse carries the token usage the provider reported (None when it reported none).
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
OPENROUTER_API_URL = "https://openrouter.ai/api/v1"
OPENAI_PROVIDERS = ("openai", "gemini", "openrouter", "openai_compatible")
_FALLBACK_PROVIDER_DEFAULT_MODELS = {"gemini": ("gemini-3.5-flash",)}
# Fields every OpenAI-style server accepts; provider-specific extras are dropped when another provider continues.
_PORTABLE_MESSAGE_KEYS = ("role", "content", "tool_calls", "tool_call_id", "name")
_PROVIDER_KEY = "_provider"
_OPENAI_DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": OPENROUTER_API_URL,
}


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
    usage: Optional[Dict[str, int]] = None
    model: str = ""


def token_usage(prompt: Optional[int], completion: Optional[int],
                total: Optional[int] = None) -> Dict[str, int]:
    prompt, completion = int(prompt or 0), int(completion or 0)
    return {"prompt_tokens": prompt, "completion_tokens": completion,
            "total_tokens": int(total or prompt + completion)}


@dataclass
class LLMConfig:
    provider: str = "scripted"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    http_referer: str = ""
    app_title: str = ""
    effort: str = ""
    max_tokens: int = 16000
    max_retries: int = 5
    timeout_seconds: float = 180.0
    fallbacks: bool = True
    fallback_models: Tuple[str, ...] = ()
    fallback_provider: str = ""
    fallback_api_key: str = ""
    fallback_base_url: str = ""
    fallback_provider_models: Tuple[str, ...] = ()

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
            http_referer=get("LLM_HTTP_REFERER"), app_title=get("LLM_APP_TITLE"), effort=get("LLM_EFFORT"),
            max_tokens=int(get("LLM_MAX_TOKENS", "16000") or 16000),
            max_retries=int(get("LLM_MAX_RETRIES", "5") or 5),
            timeout_seconds=float(get("LLM_TIMEOUT_SECONDS", "180") or 180),
            fallbacks=get("LLM_FALLBACKS", "1") not in ("0", "false", "no"),
            fallback_models=tuple(m.strip() for m in get("LLM_FALLBACK_MODELS").split(",") if m.strip()),
            fallback_provider=get("LLM_FALLBACK_PROVIDER").lower(), fallback_api_key=get("LLM_FALLBACK_API_KEY"),
            fallback_base_url=get("LLM_FALLBACK_BASE_URL"),
            fallback_provider_models=tuple(m.strip() for m in get("LLM_FALLBACK_MODELS_2").split(",") if m.strip()),
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
# Matches "PerDay", "per day", "per-day" (OpenRouter free-models-per-day) and "daily".
_DAILY_QUOTA = re.compile(r"PerDay|per[ -]day|daily", re.IGNORECASE)


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
        u = getattr(resp, "usage", None)
        usage = None
        if u is not None:
            prompt = sum(getattr(u, k, 0) or 0 for k in
                         ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            usage = token_usage(prompt, u.output_tokens)
        return LLMResponse(text=text, tool_calls=calls, stop_reason=resp.stop_reason or "end_turn", usage=usage,
                           model=getattr(resp, "model", None) or self.cfg.model)


class OpenAISession(LLMSession):
    """OpenAI Chat Completions, or any server exposing that API (OpenRouter, Gemini) via LLM_BASE_URL."""

    def __init__(self, cfg: LLMConfig, system: str, tools: Sequence[Dict[str, Any]]) -> None:
        import openai

        self._sdk = openai
        self.cfg = cfg
        headers = {k: v for k, v in (("HTTP-Referer", cfg.http_referer), ("X-Title", cfg.app_title)) if v}
        # Explicit base_url so an ambient OPENAI_BASE_URL from other tools is never used.
        self.client = openai.OpenAI(api_key=cfg.api_key or None,
                                    base_url=cfg.base_url or _OPENAI_DEFAULT_URLS.get(cfg.provider),
                                    default_headers=headers or None, max_retries=0,
                                    timeout=cfg.timeout_seconds)
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                        "parameters": t["parameters"]}} for t in tools]
        self.messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        self.models = [m for m in dict.fromkeys((cfg.model, *cfg.fallback_models)) if m]
        # (client, model, provider) in the order tried; None means self.client. A fallback provider adds its own
        # client and models.
        self.targets: List[Tuple[Any, str, str]] = [(None, m, cfg.provider) for m in self.models]
        if cfg.fallback_provider in OPENAI_PROVIDERS and cfg.fallback_api_key:
            client = openai.OpenAI(api_key=cfg.fallback_api_key,
                                   base_url=cfg.fallback_base_url or _OPENAI_DEFAULT_URLS.get(cfg.fallback_provider),
                                   max_retries=0, timeout=cfg.timeout_seconds)
            models = cfg.fallback_provider_models or _FALLBACK_PROVIDER_DEFAULT_MODELS.get(cfg.fallback_provider, ())
            self.targets += [(client, m, cfg.fallback_provider) for m in dict.fromkeys(models)]
            self.models += [m for m in models if m not in self.models]
        self.model_index = 0

    def _transport_failure(self, e: LLMError) -> bool:
        sdk, cause = self._sdk, e.__cause__
        if isinstance(cause, (sdk.APIConnectionError, sdk.APITimeoutError)):
            return True
        return isinstance(cause, sdk.APIStatusError) and (
            cause.status_code in (402, 404, 408, 429) or cause.status_code >= 500)

    def _create(self, kwargs: Dict[str, Any]) -> Tuple[Any, str]:
        failures: List[str] = []
        while True:
            client, model, provider = self.targets[self.model_index]
            last = self.model_index == len(self.targets) - 1
            call = dict(kwargs)
            call["messages"] = [_for_provider(m, provider, self.cfg.provider) for m in kwargs["messages"]]
            if provider == "openai" or self.cfg.provider == "openai":
                cap = call.pop("max_completion_tokens", None) or call.pop("max_tokens", None)
                call["max_completion_tokens" if provider == "openai" else "max_tokens"] = cap
            try:
                # Earlier models fail over at once; only the last one spends backoff retries.
                api = client or self.client
                return call_with_retries(lambda: api.chat.completions.create(**call, model=model),
                                         self._classify, max_retries=self.cfg.max_retries if last else 0), model
            except LLMError as e:
                failures.append(f"{model}: {e}")
                if last or not self._transport_failure(e):
                    if len(failures) == 1:
                        raise
                    raise type(e)("all models failed: " + " | ".join(failures)) from e
                self.model_index += 1

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
        kwargs: Dict[str, Any] = {"messages": self.messages}
        # Without a cap OpenRouter reserves credit for the model's full output length and answers 402.
        kwargs["max_completion_tokens" if self.cfg.provider == "openai" else "max_tokens"] = self.cfg.max_tokens
        if self.tools:
            kwargs["tools"] = self.tools
        resp, model = self._create(kwargs)
        choice = resp.choices[0]
        msg = choice.message
        self.messages.append({**msg.model_dump(exclude_none=True), _PROVIDER_KEY: self.targets[self.model_index][2]})
        calls: List[ToolCall] = []
        for tc in msg.tool_calls or []:
            raw = tc.function.arguments or "{}"
            try:
                args = json.loads(raw)
                calls.append(ToolCall(tc.id, tc.function.name, args if isinstance(args, dict) else {}))
            except ValueError:
                calls.append(ToolCall(tc.id, tc.function.name, {}, invalid_arguments=raw[:200]))
        u = getattr(resp, "usage", None)
        usage = token_usage(u.prompt_tokens, u.completion_tokens, u.total_tokens) if u is not None else None
        return LLMResponse(text=msg.content or "", tool_calls=calls, stop_reason=choice.finish_reason or "stop",
                           usage=usage, model=model)


def _for_provider(message: Dict[str, Any], provider: str, primary: str) -> Dict[str, Any]:
    """A message as sent to ``provider``: its own replies unchanged, another provider's reduced to portable fields."""
    source = message.get(_PROVIDER_KEY, primary)
    clean = {k: v for k, v in message.items() if k != _PROVIDER_KEY}
    return clean if source == provider else _portable(clean)


def _portable(message: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: message[k] for k in _PORTABLE_MESSAGE_KEYS if message.get(k) is not None}
    if out.get("tool_calls"):
        out["tool_calls"] = [{"id": c.get("id"), "type": "function",
                              "function": {"name": (c.get("function") or {}).get("name"),
                                           "arguments": (c.get("function") or {}).get("arguments") or "{}"}}
                             for c in out["tool_calls"]]
    if out.get("role") == "assistant" and "content" not in out:
        out["content"] = ""
    return out


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
    supported = ("anthropic", *OPENAI_PROVIDERS)
    if cfg.provider == "unset":
        raise LLMConfigError(f"LLM_PROVIDER is not set; use one of {', '.join(supported)}. "
                             "There is no offline fallback: the agent does not diagnose without a model.")
    if cfg.provider not in supported:
        raise LLMConfigError(f"LLM_PROVIDER '{cfg.provider}' is not supported; use one of {', '.join(supported)}.")
    if not cfg.api_key:
        raise LLMConfigError(f"LLM_API_KEY is not set for the {cfg.provider} provider.")
    if cfg.provider == "anthropic":
        return lambda system, tools: AnthropicSession(cfg, system, tools)
    if not cfg.model:
        raise LLMConfigError(f"LLM_MODEL must be set for the {cfg.provider} provider.")
    if cfg.provider == "openai_compatible" and not cfg.base_url:
        raise LLMConfigError("LLM_BASE_URL must be set for the openai_compatible provider "
                             f"(for OpenRouter: {OPENROUTER_API_URL}).")
    return lambda system, tools: OpenAISession(cfg, system, tools)
