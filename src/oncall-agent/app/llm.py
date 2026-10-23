import json
import os
from typing import Any

import httpx
import openai

from app.tools.registry import TOOL_DEFINITIONS

DEFAULT_BASE_URL = os.environ.get("ONCALL_LLM_BASE_URL", "http://host.docker.internal:11434/v1")
DEFAULT_MODEL = os.environ.get("ONCALL_LLM_MODEL", "qwen2.5:7b-instruct")
DEFAULT_API_KEY = os.environ.get("ONCALL_LLM_API_KEY", "ollama")
DEFAULT_NUM_CTX = int(os.environ.get("ONCALL_LLM_NUM_CTX", 4096))
DEFAULT_TIMEOUT_S = int(os.environ.get("ONCALL_LLM_TIMEOUT_S", 300))


class LLMClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        api_key: str = DEFAULT_API_KEY,
        num_ctx: int = DEFAULT_NUM_CTX,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.num_ctx = num_ctx
        self.timeout_s = timeout_s
        self._client: openai.OpenAI | None = None
        self._init_client()

    def _init_client(self) -> None:
        urls = [self.base_url, "http://localhost:11434/v1", "http://host.docker.internal:11434/v1"]
        for u in urls:
            try:
                cl = openai.OpenAI(base_url=u, api_key=self.api_key, timeout=self.timeout_s)
                cl.models.list()
                self._client = cl
                self.base_url = u
                return
            except Exception:
                continue
        self._client = openai.OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout_s)

    def get_client(self) -> openai.OpenAI:
        if self._client is None:
            self._init_client()
        return self._client or openai.OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout_s)

    def probe_capabilities(self) -> dict[str, Any]:
        client = self.get_client()
        try:
            models = client.models.list()
            model_names = [m.id for m in models.data]
            return {"status": "ok", "base_url": self.base_url, "models": model_names, "target_model": self.model}
        except Exception as e:
            return {"status": "error", "error": str(e), "base_url": self.base_url}

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Any:
        client = self.get_client()
        extra_body = {"options": {"num_ctx": self.num_ctx, "temperature": 0.1}}
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "extra_body": extra_body,
            "timeout": self.timeout_s,
        }
        if tools is not None:
            kwargs["tools"] = tools

        return client.chat.completions.create(**kwargs)


llm_client = LLMClient()
