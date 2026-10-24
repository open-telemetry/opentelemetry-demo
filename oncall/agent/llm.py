"""Thin LLM client with tool calling. Messages use the OpenAI chat format.

Only the Groq provider is implemented (OpenAI-compatible chat completions).
Another provider would translate to and from this format inside this module.
"""

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

from oncall.config import Settings, load_settings, secret

PROVIDER_BASE_URLS = {"groq": "https://api.groq.com/openai/v1"}
DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b"}
TIMEOUT_S = 60
RETRY_STATUSES = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 4
MAX_WAIT_S = 60
BAD_GENERATION_CODES = ("tool_use_failed", "output_parse_failed")
# Matches the wait in Groq's rate-limit message, e.g. "Please try again in 18.77s".
RETRY_IN = re.compile(r"try again in ([0-9.]+)s")
# A daily quota in a rate-limit message: "tokens per day (TPD)", "requests per
# day (RPD)" or any "per day"/"daily" wording, in any case.
DAILY_QUOTA = re.compile(r"per day|\b(TPD|RPD)\b|daily", re.IGNORECASE)
# Groq is behind Cloudflare, which rejects the default Python-urllib agent (error 1010).
USER_AGENT = "incident-zero-oncall/0.1"

# transport(url, headers, body) -> (status, response_json_text)
Transport = Callable[[str, dict, dict], tuple[int, str]]


class LLMError(RuntimeError):
    """The LLM call failed or returned something unusable."""

    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass
class LLMReply:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""


def _urllib_transport(url: str, headers: dict, body: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMError(f"request to {url} failed: {exc}") from exc


def to_function_tools(schemas: list[dict]) -> list[dict]:
    """Convert registry schemas ({name, description, input_schema}) to function tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["input_schema"],
            },
        }
        for s in schemas
    ]


def _retryable(status: int, text: str) -> bool:
    """Rate limits, server errors, and Groq 400s caused by a malformed generation."""
    return status in RETRY_STATUSES or (
        status == 400 and any(code in text for code in BAD_GENERATION_CODES)
    )


def _wait_s(text: str, attempt: int) -> float:
    """Seconds to wait before retrying: the provider's hint if given, else backoff."""
    match = RETRY_IN.search(text)
    wait = float(match.group(1)) + 1 if match else 2**attempt
    return min(wait, MAX_WAIT_S)


def _parse_tool_call(raw: dict) -> dict:
    fn = raw.get("function") or {}
    call = {"id": raw.get("id", ""), "name": fn.get("name", ""), "args": None}
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except json.JSONDecodeError as exc:
        call["error"] = f"arguments are not valid JSON: {exc}"
        return call
    if not isinstance(args, dict):
        call["error"] = "arguments must be a JSON object"
        return call
    call["args"] = args
    return call


@dataclass(frozen=True)
class Endpoint:
    """One entry of the fallback chain."""

    provider: str
    model: str
    key_env: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


# Entries whose daily quota ran out; skipped for the rest of the process.
EXHAUSTED: set[Endpoint] = set()


def parse_fallbacks(spec: str) -> list[Endpoint]:
    """ "groq:openai/gpt-oss-120b:GROQ_KEY_1,..." -> Endpoints (model may hold ':')."""
    endpoints = []
    for item in (part.strip() for part in spec.split(",")):
        if not item:
            continue
        provider, _, rest = item.partition(":")
        model, _, key_env = rest.rpartition(":")
        if not (provider and model and key_env):
            raise LLMError(
                f"bad LLM_FALLBACKS entry {item!r}; use provider:model:KEY_ENV_NAME"
            )
        endpoints.append(Endpoint(provider.lower(), model, key_env))
    return endpoints


def is_daily_quota(status: int, text: str) -> bool:
    """A 429 that will not clear by waiting minutes (Groq: tokens/requests per day)."""
    return status == 429 and bool(DAILY_QUOTA.search(text))


class QuotaExhausted(LLMError):
    """The endpoint's daily quota is used up; try the next one."""


class LLM:
    def __init__(
        self, settings: Settings | None = None, transport: Transport | None = None
    ):
        self.settings = settings or load_settings()
        self.transport = transport or _urllib_transport
        if self.settings.LLM_FALLBACKS:
            self.chain = parse_fallbacks(self.settings.LLM_FALLBACKS)
            self.keys = {e.key_env: secret(e.key_env) for e in self.chain}
        else:
            provider = (self.settings.LLM_PROVIDER or "").lower()
            model = self.settings.LLM_MODEL or DEFAULT_MODELS.get(provider, "")
            self.chain = [Endpoint(provider, model, "LLM_API_KEY")]
            self.keys = {"LLM_API_KEY": self.settings.LLM_API_KEY}
        for e in self.chain:
            if e.provider not in PROVIDER_BASE_URLS:
                raise LLMError(
                    f"unsupported LLM_PROVIDER {e.provider!r}; "
                    f"supported: {', '.join(PROVIDER_BASE_URLS)}"
                )
            if not self.keys.get(e.key_env):
                raise LLMError(f"{e.key_env} is not set (put it in oncall/.env)")
        first = self.chain[0]
        self.provider, self.model = first.provider, first.model

    def _url(self, endpoint: Endpoint) -> str:
        base = self.settings.LLM_BASE_URL or PROVIDER_BASE_URLS[endpoint.provider]
        return base.rstrip("/") + "/chat/completions"

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply:
        """Send one chat turn at temperature 0; the model must call a tool.

        Walks the fallback chain: an endpoint whose daily quota is exhausted is
        skipped for the rest of the process. reply.model names the one used.
        """
        skipped = []
        for endpoint in self.chain:
            if endpoint in EXHAUSTED:
                skipped.append(endpoint.label)
                continue
            try:
                return self._chat_one(endpoint, messages, tools)
            except QuotaExhausted:
                EXHAUSTED.add(endpoint)
                skipped.append(endpoint.label)
        raise LLMError(
            f"all LLM endpoints are out of daily quota: {', '.join(skipped)}",
            status=429,
        )

    def _chat_one(
        self, endpoint: Endpoint, messages: list[dict], tools: list[dict]
    ) -> LLMReply:
        body = {
            "model": endpoint.model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": self.settings.LLM_MAX_TOKENS,
        }
        if tools:
            body["tools"] = to_function_tools(tools)
            body["tool_choice"] = "required"
        headers = {
            "Authorization": f"Bearer {self.keys[endpoint.key_env]}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        url = self._url(endpoint)
        status, text = 0, ""
        for attempt in range(MAX_ATTEMPTS):
            try:
                status, text = self.transport(url, headers, body)
            except LLMError:
                # Network errors (DNS, refused, timeout) get the same backoff as 5xx.
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(_wait_s("", attempt))
                continue
            if is_daily_quota(status, text):
                raise QuotaExhausted(
                    f"{endpoint.label} daily quota exhausted: {text[:300]}",
                    status=status,
                    body=text,
                )
            if not _retryable(status, text) or attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(_wait_s(text, attempt))
        if status != 200:
            raise LLMError(
                f"{endpoint.provider} returned HTTP {status}: {text[:500]}",
                status=status,
                body=text,
            )
        try:
            data = json.loads(text)
            message = data["choices"][0]["message"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"unexpected {endpoint.provider} response: {text[:500]}"
            ) from exc
        return LLMReply(
            text=message.get("content") or "",
            tool_calls=[_parse_tool_call(c) for c in message.get("tool_calls") or []],
            usage=data.get("usage") or {},
            model=endpoint.label,
        )
