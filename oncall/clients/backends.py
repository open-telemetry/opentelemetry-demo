from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import httpx

from oncall.config import settings

TIMEOUT = 15


def prom_query(expr: str) -> list[dict[str, Any]]:
    response = httpx.get(f"{settings.PROM_URL}/api/v1/query", params={"query": expr}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["data"]["result"]


@lru_cache(maxsize=1)
def opensearch_url() -> str:
    """In host mode Docker publishes OpenSearch's 9200 on a random host port, so ask Docker for it."""
    if settings.ONCALL_MODE != "host" or os.getenv("OPENSEARCH_URL"):
        return settings.OPENSEARCH_URL
    mapping = docker("port", "opensearch", "9200").strip().splitlines()
    return f"http://localhost:{mapping[0].rsplit(':', 1)[-1]}" if mapping else settings.OPENSEARCH_URL


def opensearch_search(body: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(f"{opensearch_url()}/otel-logs-*/_search", json=body, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=1)
def jaeger_url() -> str:
    """First Jaeger base URL that answers. In host mode 16686 is only published by compose.oncall.yaml;
    otherwise Docker picks a random port, and the shop's proxy always serves Jaeger under /jaeger/ui."""
    candidates = [settings.JAEGER_URL]
    if settings.ONCALL_MODE == "host" and not os.getenv("JAEGER_URL"):
        mapping = docker("port", "jaeger", "16686").strip().splitlines()
        if mapping:
            candidates.append(f"http://localhost:{mapping[0].rsplit(':', 1)[-1]}/jaeger/ui")
        candidates.append("http://localhost:8080/jaeger/ui")
    for url in candidates:
        try:
            if httpx.get(f"{url}/api/v3/services", timeout=3).status_code == 200:
                return url
        except httpx.HTTPError:
            continue
    return settings.JAEGER_URL


def _jaeger_api() -> str:
    return f"{jaeger_url()}/api/v3"


def jaeger_services() -> list[str]:
    response = httpx.get(f"{_jaeger_api()}/services", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["services"]


def jaeger_spans(service: str, window_minutes: int, num_traces: int) -> list[dict[str, Any]]:
    """Flatten Jaeger's OTLP-shaped, possibly multi-chunk reply into spans carrying only a service name."""
    now = datetime.now(timezone.utc)
    params = {
        "query.service_name": service,
        "query.start_time_min": (now - timedelta(minutes=window_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query.start_time_max": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query.num_traces": num_traces,
    }
    response = httpx.get(f"{_jaeger_api()}/traces", params=params, timeout=18)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    spans = []
    for chunk in _json_chunks(response.text):
        for resource_spans in chunk.get("result", {}).get("resourceSpans", []):
            attrs = {a["key"]: a["value"].get("stringValue") for a in resource_spans["resource"]["attributes"]}
            for scope in resource_spans["scopeSpans"]:
                for span in scope["spans"]:
                    spans.append({**span, "service": attrs.get("service.name", "unknown")})
    return spans


def _json_chunks(text: str) -> list[dict[str, Any]]:
    decoder, index, chunks = json.JSONDecoder(), 0, []
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return chunks
        chunk, index = decoder.raw_decode(text, index)
        chunks.append(chunk)


def docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:2])} failed: {result.stderr.strip()[:200]}")
    return result.stdout
