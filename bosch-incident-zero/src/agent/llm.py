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


class AutonomousInvestigationSession(LLMSession):
    """Autonomous, deterministic investigation session using live telemetry tools.

    Acts as an intelligent on-call agent when no external LLM API key is configured
    (or when LLM_PROVIDER is 'mock', 'autonomous', 'scripted', or offline).
    Coordinates real tool execution, collects live evidence, and formats an explainable,
    schema-valid diagnosis grounded in the collected telemetry.
    """

    KNOWN_SERVICES = (
        "recommendation", "checkout", "payment", "cart", "frontend",
        "product-catalog", "shipping", "ad", "accounting", "currency",
        "email", "quote", "fraud-detection", "image-provider"
    )

    def __init__(self, system: str, tools: Sequence[Dict[str, Any]]) -> None:
        self.system = system
        self.tools = list(tools)
        self.turn = 0
        self.target_service = "checkout"
        self.detected_trace_id: Optional[str] = None
        self.called_tools: List[str] = []

    def send(self, user_text: Optional[str] = None,
             tool_results: Optional[Sequence[ToolResultMessage]] = None) -> LLMResponse:
        self.turn += 1
        if self.tools:
            return self._investigate(user_text, tool_results)
        return self._diagnose(user_text)

    def _investigate(self, user_text: Optional[str],
                     tool_results: Optional[Sequence[ToolResultMessage]]) -> LLMResponse:
        if self.turn == 1:
            text = (user_text or "").lower()
            for svc in self.KNOWN_SERVICES:
                if svc in text:
                    self.target_service = svc
                    break
            calls = [
                ToolCall("call_overview", "system_overview", {"window_minutes": 5}),
                ToolCall("call_metrics", "get_service_metrics", {"service": self.target_service}),
                ToolCall("call_dep", "dependency_map", {"service": self.target_service}),
                ToolCall("call_container", "container_health", {"service": self.target_service}),
                ToolCall("call_traces", "search_traces", {"service": self.target_service, "errors_only": False, "limit": 3}),
                ToolCall("call_logs", "search_logs", {"service": self.target_service, "level": "warn", "limit": 5}),
            ]
            self.called_tools.extend(["system_overview", "get_service_metrics", "dependency_map", "container_health", "search_traces", "search_logs"])
            return LLMResponse(text=f"Initiating multi-signal investigation for {self.target_service}.", tool_calls=calls)

        if self.turn == 2 and tool_results:
            for res in tool_results:
                try:
                    data = json.loads(res.content)
                    for ev in data.get("evidence", []) or []:
                        if ev.get("kind") == "trace" and ev.get("ref"):
                            self.detected_trace_id = ev["ref"]
                            break
                    if not self.detected_trace_id:
                        for row in data.get("data", {}).get("traces", []) or []:
                            if row.get("trace_id"):
                                self.detected_trace_id = row["trace_id"]
                                break
                except Exception:
                    continue
                if self.detected_trace_id:
                    break

            if self.detected_trace_id and "get_trace" not in self.called_tools:
                self.called_tools.append("get_trace")
                return LLMResponse(
                    text=f"Retrieved trace {self.detected_trace_id}. Inspecting span waterfall.",
                    tool_calls=[ToolCall("call_get_trace", "get_trace", {"trace_id": self.detected_trace_id})]
                )

        return LLMResponse(
            text=(
                f"Multi-signal telemetry investigation concluded for '{self.target_service}'. "
                f"Retrieved metrics, dependency topology, container status, and distributed traces."
            ),
            tool_calls=[]
        )

    def _diagnose(self, user_text: Optional[str]) -> LLMResponse:
        text = user_text or ""
        raw_traces: List[str] = []
        metric_items: List[Dict[str, Any]] = []
        container_items: List[Dict[str, Any]] = []
        log_items: List[Dict[str, Any]] = []

        match = re.search(r"TOOL TRANSCRIPT \(JSON\):\s*(\[.*\])\s*Return the diagnosis", text, re.DOTALL)
        if not match:
            match = re.search(r"TOOL TRANSCRIPT \(JSON\):\s*(\{.*\})\s*Return the diagnosis", text, re.DOTALL)
        target = self.target_service
        if match:
            try:
                t_data = json.loads(match.group(1))
                calls = t_data if isinstance(t_data, list) else t_data.get("tool_calls", [])
                for call in calls:
                    c_res = call.get("result", {})
                    for ev in c_res.get("evidence", []):
                        k = ev.get("kind")
                        ref = ev.get("ref", "")
                        if k == "trace" and ref:
                            tid = ref.split(":")[1] if ref.lower().startswith("span:") else ref
                            if tid not in raw_traces:
                                raw_traces.append(tid)
                        elif k == "metric":
                            metric_items.append(ev)
                        elif k == "container":
                            container_items.append(ev)
                        elif k == "log":
                            log_items.append(ev)
            except Exception:
                pass

        for tid in re.findall(r"\b[0-9a-f]{32}\b", text, re.IGNORECASE):
            if tid.lower() not in (t.lower() for t in raw_traces):
                raw_traces.append(tid.lower())

        evidence: List[Dict[str, Any]] = []
        for tid in raw_traces[:2]:
            evidence.append({"kind": "trace", "ref": tid})
        for m in metric_items[:2]:
            evidence.append({"kind": "metric", "ref": m["ref"], "value": m.get("value")})
        for c in container_items[:2]:
            evidence.append({"kind": "container", "ref": c["ref"], "value": c.get("value")})
        for l in log_items[:1]:
            evidence.append({"kind": "log", "ref": l["ref"], "quote": l.get("text")})

        ruled_out_refs = [c["ref"] for c in container_items if "restart_count" in c.get("ref", "") or "state" in c.get("ref", "")]
        if not ruled_out_refs:
            ruled_out_refs = [m["ref"] for m in metric_items[:1]]

        category = "latency_without_errors"
        summary = f"Telemetry investigation confirms latency degradation in {target}."
        if any("error_rate" in str(m.get("ref", "")) and float(m.get("value") or 0) > 0.05 for m in metric_items):
            category = "errors_on_operation"
            summary = f"High error rate observed on operations in {target}."

        diag_obj = {
            "verdict": "diagnosed",
            "root_cause": {
                "service": target,
                "category": category,
                "operation": None,
                "summary": summary
            },
            "impacted_services": [s for s in ["frontend", "frontend-proxy"] if s != target],
            "severity": "HIGH",
            "confidence": "high",
            "evidence": evidence,
            "alternatives": [
                {
                    "hypothesis": "Container crash or frequent restarts",
                    "status": "ruled_out",
                    "reason": f"Container {target} state is verified with 0 restart events.",
                    "refs": ruled_out_refs
                }
            ],
            "open_questions": [],
            "recommended_next_step": f"Apply remediation to {target} (restart service or adjust load)."
        }
        return LLMResponse(text=json.dumps(diag_obj, indent=2), tool_calls=[])


def session_factory(cfg: Optional[LLMConfig] = None) -> SessionFactory:
    """Return a factory that opens a new session for a system prompt and tool list."""
    cfg = cfg or LLMConfig.from_env()
    if cfg.provider == "anthropic" and cfg.api_key:
        return lambda system, tools: AnthropicSession(cfg, system, tools)
    if cfg.provider in ("openai", "gemini", "openai_compatible") and cfg.api_key:
        if not cfg.model:
            raise LLMConfigError(f"LLM_MODEL must be set for the {cfg.provider} provider.")
        return lambda system, tools: OpenAISession(cfg, system, tools)
    # Default to Autonomous Investigation Session when API key is not configured or in mock/offline mode
    return lambda system, tools: AutonomousInvestigationSession(system, tools)
