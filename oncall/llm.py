from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from oncall.config import settings


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict[str, Any]]
    usage: dict[str, Any]


class LLMClient:
    def __init__(self, max_calls: int | None = None) -> None:
        self.calls = 0
        self.max_calls = max_calls if max_calls is not None else settings.MAX_LLM_CALLS
        self._client: Any = None

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if self.calls >= self.max_calls:
            raise RuntimeError(f"LLM call cap reached ({self.max_calls})")
        self.calls += 1
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for LLMClient") from exc
        if self._client is None:
            self._client = OpenAI(api_key=settings.LLM_API_KEY or None, base_url=settings.LLM_BASE_URL or None)
        response = self._client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tools=tools,
            temperature=temperature,
            response_format=response_format,
        )
        choice = response.choices[0]
        calls = [
            {
                "id": call.id,
                "name": call.function.name,
                "arguments": json.loads(call.function.arguments),
            }
            for call in (choice.message.tool_calls or [])
        ]
        usage = response.usage.model_dump() if response.usage else {}
        return LLMResponse(choice.message.content or "", calls, usage)


class FakeLLM:
    def __init__(self, script: list[LLMResponse | dict[str, Any] | str]) -> None:
        self.script = list(script)
        self.calls = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        del messages, tools, temperature, response_format
        if not self.script:
            raise RuntimeError("FakeLLM script exhausted")
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, LLMResponse):
            return item
        if isinstance(item, str):
            return LLMResponse(item, [], {})
        return LLMResponse(item.get("content", ""), item.get("tool_calls", []), item.get("usage", {}))
