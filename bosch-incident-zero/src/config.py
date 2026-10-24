"""Configuration loader for Bosch Incident Zero."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from .telemetry.discovery import docker_host_url


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
        # Human approval is compulsory; REQUIRE_HUMAN_APPROVAL is deliberately not read.
        self.require_human_approval: bool = True
        self.dry_run_mode: bool = get_bool("DRY_RUN_MODE", True)
        self.approval_timeout_seconds: int = int(get_val("APPROVAL_TIMEOUT_SECONDS", "120"))
        self.approval_ttl_seconds: int = int(get_val("APPROVAL_TTL_SECONDS", "120"))
        # Default only: the real settle time is BLOCKED on the Action API contract.
        self.action_settle_seconds: int = int(get_val("ACTION_SETTLE_SECONDS", "120"))
        self.chat_ui_port: int = int(get_val("CHAT_UI_PORT", "8799"))
        self.deploy_platform: str = get_val("DEPLOY_PLATFORM", "docker").strip().lower()

        # Observability Endpoints
        self.jaeger_url: str = get_val("JAEGER_URL", "http://localhost:8080")
        self.prometheus_url: str = get_val("PROMETHEUS_URL", "http://localhost:9090")
        opensearch_url = os.environ.get("OPENSEARCH_URL", file_env.get("OPENSEARCH_URL", ""))
        if not opensearch_url and get_bool("DISCOVER_DOCKER_PORTS", True):
            # The demo publishes OpenSearch on a random host port.
            opensearch_url = docker_host_url("opensearch", 9200) or ""
        self.opensearch_url: str = opensearch_url or "http://localhost:9200"
        self.frontend_proxy_url: str = get_val("FRONTEND_PROXY_URL", "http://localhost:8080")

        # Fault Injection
        self.faultctl_binary_path: str = get_val("FAULTCTL_BINARY_PATH", "")

        # Action API (BLOCKED until the organisers publish the contract; no default URL is assumed)
        self.action_api_endpoint: str = get_val("ACTION_API_ENDPOINT", "")
        self.action_api_catalog_path: str = get_val("ACTION_API_CATALOG", "")
        self.action_api_timeout: int = int(get_val("ACTION_API_TIMEOUT_SECONDS", "10"))

        # Storage paths
        self.audit_log_path: str = get_val("AUDIT_LOG_PATH", "./audit_logs/audit.jsonl")
        self.report_output_dir: str = get_val("REPORT_OUTPUT_DIR", "./incident_output")

    def resolve_path(self, value: str | Path) -> Path:
        """Resolve a configured path against the project root when it is relative."""
        path = Path(value)
        return path if path.is_absolute() else self.root_dir / path

    def to_dict(self) -> Dict[str, Any]:
        """Return safe representation of settings (excluding secrets)."""
        return {
            "environment": self.environment,
            "log_level": self.log_level,
            "kill_switch_enabled": self.kill_switch_enabled,
            "kill_switch_file": self.kill_switch_file,
            "require_human_approval": self.require_human_approval,
            "dry_run_mode": self.dry_run_mode,
            "approval_timeout_seconds": self.approval_timeout_seconds,
            "approval_ttl_seconds": self.approval_ttl_seconds,
            "action_settle_seconds": self.action_settle_seconds,
            "deploy_platform": self.deploy_platform,
            "action_api_configured": bool(self.action_api_endpoint and self.action_api_catalog_path),
            "jaeger_url": self.jaeger_url,
            "prometheus_url": self.prometheus_url,
            "opensearch_url": self.opensearch_url,
            "frontend_proxy_url": self.frontend_proxy_url,
            "audit_log_path": self.audit_log_path,
        }
