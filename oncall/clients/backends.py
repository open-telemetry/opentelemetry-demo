from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from oncall.config import settings

TIMEOUT = 15


def prom_query(expr: str) -> list[dict[str, Any]]:
    response = httpx.get(f"{settings.PROM_URL}/api/v1/query", params={"query": expr}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["data"]["result"]


def opensearch_search(body: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(f"{settings.OPENSEARCH_URL}/otel-logs-*/_search", json=body, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _jaeger_api() -> str:
    return f"{settings.JAEGER_URL}/api/v3"


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
