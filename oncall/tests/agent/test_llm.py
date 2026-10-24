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


@pytest.mark.parametrize("code", llm_mod.BAD_GENERATION_CODES)
def test_retries_bad_generation(monkeypatch, code):
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    failed = json.dumps({"error": {"code": code, "message": "bad output"}})
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


def test_rate_limit_waits_as_long_as_groq_asks(monkeypatch):
    waits = []
    monkeypatch.setattr(llm_mod.time, "sleep", waits.append)
    limited = (
        '{"error": {"message": "Rate limit reached. Please try again in 18.77s."}}'
    )
    transport = FakeTransport((429, limited), (200, groq_response(content="ok")))
    assert LLM(settings(), transport).chat([], []).text == "ok"
    assert waits == [pytest.approx(19.77)]


def test_wait_is_capped():
    assert llm_mod._wait_s("Please try again in 500s", 0) == llm_mod.MAX_WAIT_S
    assert llm_mod._wait_s("no hint", 2) == 4


def test_network_error_is_retried(monkeypatch):
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    calls = []

    def flaky(url, headers, body):
        calls.append(1)
        if len(calls) < 3:
            raise LLMError("request failed: getaddrinfo failed")
        return 200, groq_response(content="hi")

    reply = LLM(settings(), transport=flaky).chat([], [])
    assert reply.text == "hi" and len(calls) == 3


TPD_429 = (
    '{"error":{"message":"Rate limit reached for model `openai/gpt-oss-20b` on '
    "tokens per day (TPD): Limit 200000, Used 198294, Requested 3976. Please try "
    'again in 16m20.64s.","code":"rate_limit_exceeded"}}'
)
TPM_429 = (
    '{"error":{"message":"Rate limit reached on tokens per minute (TPM): '
    'Limit 8000, Used 7000. Please try again in 2.5s."}}'
)
CHAIN = "groq:openai/gpt-oss-120b:KEY_A,groq:openai/gpt-oss-20b:KEY_B"


@pytest.fixture
def chain(monkeypatch):
    monkeypatch.setenv("KEY_A", "key-a")
    monkeypatch.setenv("KEY_B", "key-b")
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    llm_mod.EXHAUSTED.clear()
    yield Settings(LLM_FALLBACKS=CHAIN)
    llm_mod.EXHAUSTED.clear()


def test_parse_fallbacks_keeps_model_slashes_and_colons():
    chain = llm_mod.parse_fallbacks("groq:openai/gpt-oss-120b:K1, groq:a:b:c:K2")
    assert [(e.model, e.key_env) for e in chain] == [
        ("openai/gpt-oss-120b", "K1"),
        ("a:b:c", "K2"),
    ]
    with pytest.raises(LLMError):
        llm_mod.parse_fallbacks("groq:only-model")


def test_daily_quota_moves_to_next_endpoint_and_stays_skipped(chain):
    transport = FakeTransport(
        (429, TPD_429),
        (200, groq_response(content="from 20b")),
        (200, groq_response(content="again 20b")),
    )
    llm = LLM(chain, transport)
    first = llm.chat([], [])
    assert (first.text, first.model) == ("from 20b", "groq:openai/gpt-oss-20b")
    assert [r[2]["model"] for r in transport.requests] == [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ]
    assert [r[1]["Authorization"] for r in transport.requests] == [
        "Bearer key-a",
        "Bearer key-b",
    ]
    # A new client in the same process still skips the exhausted endpoint.
    second = LLM(chain, transport).chat([], [])
    assert second.model == "groq:openai/gpt-oss-20b"
    assert len(transport.requests) == 3


def test_per_minute_429_is_retried_on_the_same_endpoint(chain):
    transport = FakeTransport((429, TPM_429), (200, groq_response(content="ok")))
    reply = LLM(chain, transport).chat([], [])
    assert reply.model == "groq:openai/gpt-oss-120b"
    assert [r[2]["model"] for r in transport.requests] == ["openai/gpt-oss-120b"] * 2
    assert not llm_mod.EXHAUSTED


def test_all_endpoints_exhausted_raises(chain):
    transport = FakeTransport((429, TPD_429), (429, TPD_429))
    with pytest.raises(LLMError, match="out of daily quota") as err:
        LLM(chain, transport).chat([], [])
    assert err.value.status == 429


def test_missing_key_env_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr("oncall.config.DEFAULT_ENV_FILE", tmp_path / "none.env")
    monkeypatch.delenv("KEY_Z", raising=False)
    with pytest.raises(LLMError, match="KEY_Z is not set"):
        LLM(Settings(LLM_FALLBACKS="groq:m:KEY_Z"))


def test_single_endpoint_reply_names_its_model():
    reply = LLM(settings(), FakeTransport((200, groq_response(content="x")))).chat(
        [], []
    )
    assert reply.model == "groq:openai/gpt-oss-120b"
