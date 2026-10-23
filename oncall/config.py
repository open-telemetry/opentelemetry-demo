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


def _settings() -> Settings:
    mode = os.getenv("ONCALL_MODE", "docker").lower()
    host = mode == "host"
    return Settings(
        JAEGER_URL=os.getenv("JAEGER_URL", "http://localhost:8080/jaeger/ui" if host else "http://jaeger:16686/jaeger/ui"),
        PROM_URL=os.getenv("PROM_URL", "http://localhost:9090" if host else "http://prometheus:9090"),
        OPENSEARCH_URL=os.getenv("OPENSEARCH_URL", "http://localhost:9200" if host else "http://opensearch:9200"),
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
