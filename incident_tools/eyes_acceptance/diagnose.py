"""Credential-safe, inference-only diagnostics for the unchanged Eyes Router."""
import argparse
from copy import deepcopy
import errno
import json
import os
import socket
import ssl
import time
from urllib import error, parse

from incident_tools.eyes.runtime import load, Router
from .configuration import OPENAI_ENDPOINT, OPENAI_KEY_ENV, model_probe_budget

PROBE_MESSAGES = [
    {"role": "system", "content": 'Return exactly the JSON object {"ready":true}. No markdown.'},
    {"role": "user", "content": "Connection check only; no incident or telemetry."},
]


def category(exc):
    if isinstance(exc, error.HTTPError):
        return "http_error"
    cause = exc.reason if isinstance(exc, error.URLError) else exc
    if isinstance(cause, ssl.SSLCertVerificationError):
        return "tls_certificate_verification_failed"
    if isinstance(cause, ssl.SSLError):
        return "tls_error"
    if isinstance(cause, socket.gaierror):
        return "dns_error"
    if isinstance(cause, TimeoutError):
        return "timeout"
    if isinstance(cause, ConnectionRefusedError):
        return "connection_refused"
    if isinstance(cause, OSError) and cause.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
        return "network_unreachable"
    if isinstance(cause, OSError) or isinstance(exc, error.URLError):
        return "network_error"
    return "transport_error"


def response_metadata(raw, backend):
    result = {"response_bytes": len(raw)}
    if len(raw) > 262144:
        return {**result, "category": "response_too_large"}
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError, TypeError):
        return {**result, "category": "response_json_invalid"}
    try:
        if backend == "ollama":
            content = body["message"]["content"]
        else:
            choice = body["choices"][0]
            finish = choice.get("finish_reason")
            result["finish_reason"] = finish if finish in (
                "stop", "length", "tool_calls", "content_filter", "function_call") else "other"
            content = choice["message"]["content"]
        if not isinstance(content, str):
            return {**result, "category": "response_schema_invalid"}
        json.loads(content)
    except (KeyError, TypeError, IndexError):
        return {**result, "category": "response_schema_invalid"}
    except ValueError:
        return {**result, "category": "content_not_json"}
    return {**result, "category": "response_received", "content_json_valid": True}


class TracedResponse:
    def __init__(self, response, entry, backend, started):
        self.response, self.entry, self.backend, self.started = response, entry, backend, started

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        return self.response.__exit__(*args)

    def read(self, size):
        try:
            raw = self.response.read(size)
            self.entry.update(response_metadata(raw, self.backend))
            return raw
        except Exception as exc:
            self.entry.update(category=category(exc), phase="response_body")
            raise
        finally:
            self.entry["elapsed_seconds"] = round(time.monotonic() - self.started, 3)


def trace_open(original, attempts, providers):
    def opened(req, timeout):
        payload = json.loads(req.data)
        provider = next((p for p in providers if p["model"] == payload["model"]
                         and req.full_url.startswith(p["endpoint"].rstrip("/") + "/")), {})
        entry = {"attempt": len(attempts) + 1, "timeout_seconds": round(timeout, 3),
                 "phase": "connection_or_headers", "category": "request_started"}
        attempts.append(entry)
        started = time.monotonic()
        try:
            response = original(req, timeout=timeout)
            entry["http_status"] = getattr(response, "status", None)
            entry["phase"] = "response_body"
            return TracedResponse(response, entry, provider.get("backend"), started)
        except Exception as exc:
            entry.update(category=category(exc), elapsed_seconds=round(time.monotonic() - started, 3))
            if isinstance(exc, error.HTTPError):
                entry["http_status"] = exc.code
                exc.close()
            raise
    return opened


def redact(value, secrets):
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
    return value


def diagnose(config):
    attempts, secrets, router = [], [], None
    result = {"probe_succeeded": False, "attempts": attempts,
              "telemetry_queried": False, "practice_fault_executed": False,
              "note": "One inference attempt per selected provider; no telemetry, Docker, injection or file writes."}
    try:
        cfg, _, _, _ = load(config)
        models = deepcopy(cfg["models"])
        for slot in ("cloud", "local"):
            provider = models.get(slot)
            if isinstance(provider, dict):
                secret = os.environ.get(provider.get("api_key_env", ""))
                if secret:
                    secrets.append(secret)
                provider["retries"] = 0
        router = Router(models)
        providers = [models[slot] for slot in router.order]
        result["model_configuration"] = router.public_configuration
        cloud = models.get("cloud", {})
        if cloud.get("api_key_env") == OPENAI_KEY_ENV:
            result["openai_endpoint_matches"] = cloud.get("endpoint", "").rstrip("/") == OPENAI_ENDPOINT
        result["environment_key_has_outer_whitespace"] = any(secret != secret.strip() for secret in secrets)
        result["request_budget_seconds"] = model_probe_budget(router)
        original = router.opener.open
        router.opener.open = trace_open(original, attempts, providers)
        answer, identity = router.decide(PROBE_MESSAGES, result["request_budget_seconds"])
        result["probe_succeeded"] = answer == {"ready": True}
        result["model_probe"] = identity
        result["category"] = "success" if result["probe_succeeded"] else "unexpected_probe_content"
    except Exception:
        result["category"] = attempts[-1]["category"] if attempts else (
            "configuration_error" if router is None else "no_request_within_budget")
    result["next_step"] = {
        "success": "The model-only request works. Re-run acceptance preflight; metrics readiness remains a separate check.",
        "http_error": "Use http_status to check authentication/access (401/403), endpoint/model (404), quota (429), or provider failure (5xx).",
        "timeout": "Compare the configured timeout with measured provider first-byte latency and the request budget; the key and model are not established as invalid.",
        "tls_certificate_verification_failed": "Check the Python/Ubuntu CA trust store and any organization TLS interception certificate.",
        "tls_error": "Check Python/OpenSSL and the network TLS path.",
        "dns_error": "Check name resolution inside the same Ubuntu environment.",
        "connection_refused": "Verify the configured endpoint host and port.",
        "network_unreachable": "Check WSL routes, VPN and IPv4/IPv6 reachability.",
        "network_error": "Check the Ubuntu network path; no raw exception or credentials are printed.",
        "content_not_json": "The provider returned content that does not meet the Router JSON contract; inspect finish_reason for truncation.",
        "response_schema_invalid": "The response did not match the configured backend envelope.",
        "response_json_invalid": "The HTTP body was not valid JSON.",
        "response_too_large": "The response exceeded the existing Router byte limit.",
        "unexpected_probe_content": "The response parsed, but did not equal the expected readiness object.",
        "configuration_error": "Check model, endpoint, enabled route and the configured API-key environment variable.",
    }.get(result["category"], "Inspect the attempt categories and selected model configuration.")
    return redact(result, secrets)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    result = diagnose(args.config)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["probe_succeeded"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
