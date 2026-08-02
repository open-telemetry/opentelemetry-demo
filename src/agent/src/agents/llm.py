#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import os

import httpx
from langchain_openai import ChatOpenAI

def default_base_url():
    host = os.getenv("DEMO_LLM_ENDPOINT", "demo-llm")
    port = os.getenv("DEMO_LLM_PORT", "8012")
    return f"http://{host}:{port}/v1"


class ChatLLM(ChatOpenAI):
    def __init__(self, **kwargs):
        base_url = os.getenv("LLM_BASE_URL") or default_base_url()
        model_name = os.getenv("LLM_MODEL") or (
            os.getenv("DEMO_LLM_MODEL_NAME", "demo-llm")
            if base_url == default_base_url()
            else "default"
        )
        llm_tls_verify = os.getenv("LLM_TLS_VERIFY", "True").lower() == "true"

        if "http_async_client" not in kwargs:
            kwargs["http_async_client"] = httpx.AsyncClient(verify=llm_tls_verify)
        kwargs.setdefault("openai_api_base", base_url)
        kwargs.setdefault("model", model_name)
        # demo-llm ignores the key, but the OpenAI client requires one to be set.
        kwargs.setdefault("api_key", os.getenv("API_KEY") or "sk-dummy")

        super().__init__(**kwargs)
