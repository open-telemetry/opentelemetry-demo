#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import os

import httpx
from langchain_openai import ChatOpenAI
from src.agents.patch_vcr import VCR


class ChatLLM(ChatOpenAI):
    def __init__(self, **kwargs):
        model_name = os.getenv("LLM_MODEL", "default")
        use_vcr = os.getenv("use_vcr", False)
        cassette_name = ""
        if use_vcr:
            cassette_name = f"{model_name.replace('/', '_')}_casette.yaml"
        if "http_async_client" not in kwargs:
            kwargs["http_async_client"] = httpx.AsyncClient(verify=False)
        kwargs.setdefault("openai_api_base", os.getenv("LLM_BASE_URL"))
        kwargs.setdefault("model", model_name)
        super().__init__(**kwargs)

        object.__setattr__(self, "_use_vcr", use_vcr)
        object.__setattr__(self, "_cassette_name", cassette_name)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if getattr(self, "_use_vcr", False):
            with VCR.use_cassette(self._cassette_name):
                return super()._generate(messages, stop, run_manager, **kwargs)
        return super()._generate(messages, stop, run_manager, **kwargs)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        if getattr(self, "_use_vcr", False):
            if getattr(self, "_use_vcr", False):
                return await super()._agenerate(messages, stop, run_manager, **kwargs)
        return await super()._agenerate(messages, stop, run_manager, **kwargs)
