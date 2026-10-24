"""Settings loaded from the process environment and oncall/.env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

DEFAULT_ENV_FILE = Path(__file__).parent / ".env"


@dataclass(frozen=True)
class Settings:
    PROM_URL: str | None = None
    JAEGER_URL: str | None = None
    OPENSEARCH_URL: str | None = None
    OPENSEARCH_LOG_INDEX: str | None = None
    COMPOSE_PROJECT_NAME: str = "opentelemetry-demo"
    TELEMETRY_BACKEND: str = "live"
    OFFLINE_DIR: str | None = None
    LLM_PROVIDER: str | None = None
    LLM_MODEL: str | None = None
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_FALLBACKS: str | None = None
    LLM_MAX_TOKENS: int = 1500
    LLM_MAX_PROMPT_TOKENS: int = 6000
    MAX_STEPS: int = 8
    CONFIDENCE_MIN: float = 0.7
    RUNS_DIR: str = "runs"
    ACTION_API_URL: str | None = None
    DRY_RUN: bool = True
    KILL_SWITCH_FILE: str = ".killswitch"
    VERIFY_WINDOW_S: int = 120
    ALERT_ERROR_RATE: float = 0.05
    ALERT_P95_MS: int = 1000
    ALERT_POLL_S: int = 15


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"not a boolean: {value!r}")


def _convert(raw: str, default: object) -> object:
    if isinstance(default, bool):
        return _parse_bool(raw)
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


def secret(name: str, env_file: str | Path | None = None) -> str | None:
    """A named secret (e.g. an API key variable): process env, then oncall/.env."""
    path = Path(env_file) if env_file else DEFAULT_ENV_FILE
    value = os.environ.get(name)
    if not value and path.is_file():
        value = dotenv_values(path).get(name)
    return value or None


def load_settings(env_file: str | Path | None = None) -> Settings:
    """Load Settings: process env wins over the .env file, which wins over defaults."""
    path = Path(env_file) if env_file else DEFAULT_ENV_FILE
    file_values = dotenv_values(path) if path.is_file() else {}
    defaults = Settings()
    values = {}
    for name in Settings.__dataclass_fields__:
        raw = os.environ.get(name, file_values.get(name))
        if raw is None or raw == "":
            continue
        values[name] = _convert(raw, getattr(defaults, name))
    return Settings(**values)
