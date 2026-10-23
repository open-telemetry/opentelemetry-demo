"""Configuration loader for Bosch Incident Zero."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict


def load_env_file(filepath: Path) -> Dict[str, str]:
    """Parse key=value pairs from a .env file."""
    env_vars: Dict[str, str] = {}
    if not filepath.exists():
        return env_vars

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                k, v = stripped.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env_vars[k] = v
    return env_vars


class Settings:
    """Application settings loaded from environment and optional .env file."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path(__file__).resolve().parent.parent
        env_path = self.root_dir / ".env"
        file_env = load_env_file(env_path)

        def get_val(key: str, default: str) -> str:
            return os.environ.get(key, file_env.get(key, default))

        def get_bool(key: str, default: bool) -> bool:
            val = get_val(key, str(default)).strip().lower()
            return val in ("true", "1", "yes", "on")

        # General
        self.environment: str = get_val("ENVIRONMENT", "development")
        self.log_level: str = get_val("LOG_LEVEL", "INFO")

        # Safety Controls
        self.kill_switch_enabled: bool = get_bool("KILL_SWITCH_ENABLED", False)
        self.kill_switch_file: str = get_val("KILL_SWITCH_FILE", ".kill_switch")
        self.require_human_approval: bool = get_bool("REQUIRE_HUMAN_APPROVAL", True)
        self.dry_run_mode: bool = get_bool("DRY_RUN_MODE", True)

        # Observability Endpoints
        self.jaeger_url: str = get_val("JAEGER_URL", "http://localhost:16686")
        self.prometheus_url: str = get_val("PROMETHEUS_URL", "http://localhost:9090")
        self.opensearch_url: str = get_val("OPENSEARCH_URL", "http://localhost:9200")
        self.frontend_proxy_url: str = get_val("FRONTEND_PROXY_URL", "http://localhost:8080")

        # Fault Injection
        self.flagd_url: str = get_val("FLAGD_URL", "http://localhost:8013")
        self.flagd_config_path: str = get_val("FLAGD_CONFIG_PATH", "../src/flagd/demo.flagd.json")
        self.faultctl_binary_path: str = get_val("FAULTCTL_BINARY_PATH", "")

        # Action API
        self.action_api_endpoint: str = get_val("ACTION_API_ENDPOINT", "http://localhost:8080/action-api")
        self.action_api_timeout: int = int(get_val("ACTION_API_TIMEOUT_SECONDS", "10"))

        # Storage paths
        self.audit_log_path: str = get_val("AUDIT_LOG_PATH", "./audit_logs/audit.jsonl")
        self.report_output_dir: str = get_val("REPORT_OUTPUT_DIR", "./incident_output")

    def to_dict(self) -> Dict[str, Any]:
        """Return safe representation of settings (excluding secrets)."""
        return {
            "environment": self.environment,
            "log_level": self.log_level,
            "kill_switch_enabled": self.kill_switch_enabled,
            "kill_switch_file": self.kill_switch_file,
            "require_human_approval": self.require_human_approval,
            "dry_run_mode": self.dry_run_mode,
            "jaeger_url": self.jaeger_url,
            "prometheus_url": self.prometheus_url,
            "opensearch_url": self.opensearch_url,
            "frontend_proxy_url": self.frontend_proxy_url,
            "flagd_url": self.flagd_url,
            "audit_log_path": self.audit_log_path,
        }
