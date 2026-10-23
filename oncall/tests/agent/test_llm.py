import json

import pytest

from oncall.agent import llm as llm_mod
from oncall.agent.llm import LLM, LLMError
from oncall.config import Settings

SCHEMA = {
    "name": "get_metrics",
    "description": "Query metrics.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}


def settings(**kw) -> Settings:
    return Settings(LLM_PROVIDER="groq", LLM_API_KEY="test-key", **kw)


def groq_response(tool_calls=None, content=None) -> str:
    return json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    }
                }
            ],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        }
    )


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, url, headers, body):
        self.requests.append((url, headers, body))
        return self.responses.pop(0)


def test_request_shape_and_tool_call_parsing():
    tc = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_metrics", "arguments": '{"service": "cart"}'},
    }
    transport = FakeTransport((200, groq_response([tc])))
    reply = LLM(settings(), transport).chat(
        [{"role": "user", "content": "hi"}], [SCHEMA]
    )

    url, headers, body = transport.requests[0]
    assert url == "https://api.groq.com/openai/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["User-Agent"] == llm_mod.USER_AGENT
    assert body["model"] == llm_mod.DEFAULT_MODELS["groq"]
    assert body["temperature"] == 0
    assert body["tool_choice"] == "required"
    assert body["tools"][0] == {
        "type": "function",
        "function": {
            "name": "get_metrics",
            "description": "Query metrics.",
            "parameters": SCHEMA["input_schema"],
        },
    }
    assert reply.tool_calls == [
        {"id": "call_1", "name": "get_metrics", "args": {"service": "cart"}}
    ]
    assert reply.usage["total_tokens"] == 10


def test_model_and_base_url_from_settings():
    transport = FakeTransport((200, groq_response(content="hello")))
    llm = LLM(settings(LLM_MODEL="m1", LLM_BASE_URL="http://proxy/v1/"), transport)
    reply = llm.chat([], [])
    url, _, body = transport.requests[0]
    assert url == "http://proxy/v1/chat/completions"
    assert body["model"] == "m1"
    assert "tools" not in body
    assert reply.text == "hello"


def test_bad_arguments_json_is_reported_not_raised():
    tc = {"id": "c", "function": {"name": "get_metrics", "arguments": "{oops"}}
    reply = LLM(settings(), FakeTransport((200, groq_response([tc])))).chat(
        [], [SCHEMA]
    )
    assert reply.tool_calls[0]["args"] is None
    assert "not valid JSON" in reply.tool_calls[0]["error"]


def test_http_error_raises_llm_error():
    with pytest.raises(LLMError, match="HTTP 401"):
        LLM(settings(), FakeTransport((401, '{"error": "bad key"}'))).chat([], [])


def test_retries_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    transport = FakeTransport((429, "slow down"), (200, groq_response(content="ok")))
    assert LLM(settings(), transport).chat([], []).text == "ok"
    assert len(transport.requests) == 2


def test_malformed_response_raises_llm_error():
    with pytest.raises(LLMError, match="unexpected"):
        LLM(settings(), FakeTransport((200, '{"choices": []}'))).chat([], [])


def test_missing_key_or_unknown_provider():
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        LLM(Settings(LLM_PROVIDER="groq"))
    with pytest.raises(LLMError, match="unsupported"):
        LLM(Settings(LLM_PROVIDER="other", LLM_API_KEY="k"))


def test_retries_tool_use_failed(monkeypatch):
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    failed = '{"error": {"code": "tool_use_failed", "message": "bad tool"}}'
    transport = FakeTransport((400, failed), (200, groq_response(content="ok")))
    assert LLM(settings(), transport).chat([], []).text == "ok"


def test_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    transport = FakeTransport(*[(503, "down")] * llm_mod.MAX_ATTEMPTS)
    with pytest.raises(LLMError, match="HTTP 503"):
        LLM(settings(), transport).chat([], [])
    assert len(transport.requests) == llm_mod.MAX_ATTEMPTS


def test_other_400_is_not_retried():
    transport = FakeTransport((400, '{"error": {"code": "invalid_request"}}'))
    with pytest.raises(LLMError, match="HTTP 400"):
        LLM(settings(), transport).chat([], [])
    assert len(transport.requests) == 1
