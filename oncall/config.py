from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    JAEGER_URL: str
    PROM_URL: str
    OPENSEARCH_URL: str
    LLM_BASE_URL: str
    LLM_MODEL: str
    LLM_API_KEY: str
    DOCKER_SOCK: str
    ONCALL_MODE: str
    RUNS_DIR: str
    CONFIDENCE_THRESHOLD: float
    MAX_AGENT_STEPS: int
    MAX_LLM_CALLS: int


def _load_env_local() -> None:
    path = os.path.join(os.path.dirname(__file__), ".env.local")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key, value)


def _settings() -> Settings:
    _load_env_local()
    mode = os.getenv("ONCALL_MODE", "docker" if os.path.exists("/.dockerenv") else "host").lower()
    host = mode == "host"
    return Settings(
        JAEGER_URL=os.getenv("JAEGER_URL", "http://127.0.0.1:16686/jaeger/ui" if host else "http://jaeger:16686/jaeger/ui"),
        PROM_URL=os.getenv("PROM_URL", "http://127.0.0.1:9090" if host else "http://prometheus:9090"),
        OPENSEARCH_URL=os.getenv("OPENSEARCH_URL", "http://127.0.0.1:9200" if host else "http://opensearch:9200"),
        LLM_BASE_URL=os.getenv("LLM_BASE_URL", ""),
        LLM_MODEL=os.getenv("LLM_MODEL", ""),
        LLM_API_KEY=os.getenv("LLM_API_KEY", ""),
        DOCKER_SOCK=os.getenv("DOCKER_SOCK", "/var/run/docker.sock"),
        ONCALL_MODE=mode,
        RUNS_DIR=os.getenv("RUNS_DIR", "runs"),
        CONFIDENCE_THRESHOLD=float(os.getenv("CONFIDENCE_THRESHOLD", "0.65")),
        MAX_AGENT_STEPS=int(os.getenv("MAX_AGENT_STEPS", "12")),
        MAX_LLM_CALLS=int(os.getenv("MAX_LLM_CALLS", "40")),
    )


settings = _settings()
