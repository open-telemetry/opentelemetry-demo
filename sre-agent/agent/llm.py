"""Thin LLM client for any OpenAI-compatible /chat/completions endpoint (plain HTTP, no SDK).

Supports tool calling (function calling). Works with OpenAI, Gemini's OpenAI-compatible
endpoint, Groq, Ollama (http://localhost:11434/v1/), LiteLLM, vLLM ...
"""
import json
import time
import re

import requests

from agent import config


class LLMError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.LLM_API_KEY) or "localhost" in config.LLM_BASE_URL


_active = None   # the model that last worked (sticky for this run)


def _models() -> list:
    order = [_active] if _active else []
    for m in [config.LLM_MODEL] + config.LLM_FALLBACK_MODELS:
        if m and m not in order:
            order.append(m)
    return order


def _post(body: dict, headers: dict):
    """One model: retry briefly on 429/503. Returns the response or raises LLMError."""
    r = None
    for attempt in range(3):
        try:
            r = requests.post(config.LLM_BASE_URL + "chat/completions", json=body, headers=headers,
                              timeout=config.LLM_TIMEOUT)
        except requests.RequestException as e:
            raise LLMError(f"{body['model']}: unreachable/timeout ({type(e).__name__})") from e
        if r.status_code not in (429, 503):
            break
        try:
            wait = float(r.headers.get("retry-after", "0")) or 2 ** (attempt + 1)
        except ValueError:
            wait = 2 ** (attempt + 1)
        time.sleep(min(wait, 10))
    if r.status_code >= 400:
        raise LLMError(f"{body['model']}: HTTP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()["choices"][0]["message"]
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"{body['model']}: bad response: {r.text[:200]}") from e


def chat(messages: list, tools: list = None, temperature: float = 0.1, json_mode: bool = False) -> dict:
    """Returns the assistant message dict: {"role", "content", "tool_calls"?}.
    Tries LLM_MODEL, then LLM_FALLBACK_MODELS (on overload / not found / timeout).
    json_mode is ignored on purpose: strict response_format hangs on some providers; we parse JSON ourselves."""
    global _active
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    errors = []
    for model in _models():
        body = {"model": model, "messages": messages, "temperature": temperature}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if config.LLM_REASONING_EFFORT:
            body["reasoning_effort"] = config.LLM_REASONING_EFFORT
        try:
            msg = _post(body, headers)
            _active = model
            return msg
        except LLMError as e:
            errors.append(str(e))
    raise LLMError(" | ".join(errors))


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0) if m else text)


def chat_json(system: str, user: str) -> dict:
    msg = chat([{"role": "system", "content": system}, {"role": "user", "content": user}], json_mode=True)
    return parse_json(msg.get("content") or "")


def ping():
    out = chat_json("Reply with JSON only, no other text.", 'Return {"ok": true}')
    return f"{out} (model: {_active})"
