"""Where the read-only backends (Prometheus, Jaeger, OpenSearch) can be reached.

URLs come from .env.incident when set, otherwise from the defaults below.
OpenSearch has no fixed host port (it changes on every `make start`), so when
OPENSEARCH_URL is not set we ask Docker which port it is mapped to.
"""
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.incident"

DEFAULT_PROMETHEUS_URL = "http://localhost:9090"
# Jaeger is reached through the demo's front proxy, so its port never changes.
# Its query API lives under <JAEGER_URL>/api/v3/...
DEFAULT_JAEGER_URL = "http://localhost:8080/jaeger/ui"
DEFAULT_COMPOSE_PROJECT = "opentelemetry-demo"
DEFAULT_OPENSEARCH_CONTAINER = "opensearch"
OPENSEARCH_CONTAINER_PORT = "9200"


@dataclass
class Endpoint:
    name: str
    url: str | None  # None means we could not work out a URL
    source: str  # where the URL came from: ".env.incident", "default" or "docker port"
    error: str | None = None  # set when url is None


def load_settings() -> dict[str, str]:
    """Read .env.incident from its explicit path. Empty values count as unset."""
    if not ENV_FILE.exists():
        return {}
    return {k: v for k, v in dotenv_values(ENV_FILE).items() if v}


def docker_host_port(container: str, container_port: str) -> tuple[str | None, str | None]:
    """Ask Docker which host port a container port is published on.

    Returns (port, None) on success or (None, reason) on failure.
    """
    try:
        result = subprocess.run(
            ["docker", "port", container, container_port],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"docker not usable: {exc}"
    if result.returncode != 0:
        return None, result.stderr.strip() or f"docker port exited with {result.returncode}"
    # Output looks like "0.0.0.0:60668" then "[::]:60668"; the first line is enough.
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    port = lines[0].rsplit(":", 1)[-1] if lines else ""
    if not port.isdigit():
        return None, f"could not parse port from: {result.stdout.strip()!r}"
    return port, None


def compose_project(settings: dict[str, str] | None = None) -> str:
    settings = load_settings() if settings is None else settings
    return settings.get("COMPOSE_PROJECT", DEFAULT_COMPOSE_PROJECT)


def get_endpoints(settings: dict[str, str] | None = None) -> dict[str, Endpoint]:
    """Resolve the URL of each backend. Never raises; problems go in Endpoint.error."""
    settings = load_settings() if settings is None else settings

    def configured(key: str, default: str) -> Endpoint:
        name = key.removesuffix("_URL").lower()
        if key in settings:
            return Endpoint(name, settings[key].rstrip("/"), ".env.incident")
        return Endpoint(name, default, "default")

    prometheus = configured("PROMETHEUS_URL", DEFAULT_PROMETHEUS_URL)
    jaeger = configured("JAEGER_URL", DEFAULT_JAEGER_URL)

    if "OPENSEARCH_URL" in settings:
        opensearch = Endpoint("opensearch", settings["OPENSEARCH_URL"].rstrip("/"), ".env.incident")
    else:
        container = settings.get("OPENSEARCH_CONTAINER", DEFAULT_OPENSEARCH_CONTAINER)
        port, error = docker_host_port(container, OPENSEARCH_CONTAINER_PORT)
        if port:
            opensearch = Endpoint("opensearch", f"http://localhost:{port}", "docker port")
        else:
            opensearch = Endpoint("opensearch", None, "docker port", error)

    return {"prometheus": prometheus, "jaeger": jaeger, "opensearch": opensearch}
