import os

import httpx
from langchain_openai import ChatOpenAI

class ChatLLM(ChatOpenAI):
    def __init__(self, **kwargs):
        if "http_async_client" not in kwargs:
            kwargs["http_async_client"] = httpx.AsyncClient(verify=False)
        kwargs.setdefault("openai_api_base", os.getenv("LLM_BASE_URL"))
        kwargs.setdefault("model", os.getenv("LLM_MODEL"))
        super().__init__(**kwargs)
