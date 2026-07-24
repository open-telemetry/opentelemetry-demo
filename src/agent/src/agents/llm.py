#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import os

import httpx
from langchain_openai import ChatOpenAI
from src.agents.llm_cache import CacheKey, LLMCacheMiss, get_cache


class ChatLLM(ChatOpenAI):
    def __init__(self, is_synthetic=False, **kwargs):
        model_name = os.getenv("LLM_MODEL", "default")
        llm_tls_verify = os.getenv("LLM_TLS_VERIFY", "True").lower() == "true"
        if "http_async_client" not in kwargs:
            kwargs["http_async_client"] = httpx.AsyncClient(
                verify=llm_tls_verify
            )
        kwargs.setdefault("openai_api_base", os.getenv("LLM_BASE_URL"))
        kwargs.setdefault("model", model_name)

        api_key = os.getenv("API_KEY")
        if not api_key:
            api_key = "sk-dummy"
        kwargs.setdefault("api_key", api_key)

        super().__init__(**kwargs)

        object.__setattr__(self, "_llm_cache", get_cache(model_name))
        object.__setattr__(self, "_is_synthetic", is_synthetic)

    def _effective_mode(self, cache):
        """Cache mode to use for this call.

        Synthetic (load-generator) traffic fires a fixed, high-volume
        prompt set concurrently, so it is forced into "replay" regardless
        of LLM_CACHE_MODE: a hybrid/record fallback to the live LLM would
        make load-test runs slow, non-deterministic, and costly. Organic
        traffic (e.g. a human typing into the chatbot) keeps the
        configured process-wide mode, so custom questions still get
        recorded on the fly.
        """
        return "replay" if self._is_synthetic else cache.mode

    def _cache_context(self, messages, stop, kwargs):
        """Return (cache, payload) or (None, None) when not cacheable.

        Streaming, structured-output, and Responses API requests fall
        through to the regular client.
        """
        cache = getattr(self, "_llm_cache", None)
        if cache is None:
            return None, None
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        if (
            payload.get("stream")
            or "response_format" in payload
            or self._use_responses_api(payload)
        ):
            return None, None
        return cache, payload

    def _cached_result(self, cache, key, mode):
        cached = cache.lookup(key) if mode != "record" else None
        if cached is not None:
            return self._create_chat_result(cached)
        if mode == "replay":
            raise LLMCacheMiss(
                "no cached LLM response matches this request; run with "
                "LLM_CACHE_MODE=hybrid and a configured LLM to record one"
            )
        return None

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        cache, payload = self._cache_context(messages, stop, kwargs)
        if cache is None:
            return super()._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )
        mode = self._effective_mode(cache)
        key = CacheKey(payload)
        result = self._cached_result(cache, key, mode)
        if result is not None:
            return result
        response = self._response_dict(self.client.create(**payload))
        cache.store(key, response)
        return self._create_chat_result(response)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        cache, payload = self._cache_context(messages, stop, kwargs)
        if cache is None:
            return await super()._agenerate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )
        mode = self._effective_mode(cache)
        key = CacheKey(payload)
        result = self._cached_result(cache, key, mode)
        if result is not None:
            return result
        response = await cache.fetch(key, lambda: self._alive_call(payload))
        return self._create_chat_result(response)

    async def _alive_call(self, payload):
        return self._response_dict(await self.async_client.create(**payload))

    @staticmethod
    def _response_dict(response):
        if hasattr(response, "model_dump"):
            return response.model_dump(mode="json")
        return response
