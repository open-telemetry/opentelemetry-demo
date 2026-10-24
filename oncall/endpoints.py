"""Resolve telemetry backend URLs: env var, then oncall/.env, then Docker, then defaults."""

import logging
import re
import subprocess

from oncall.config import Settings, load_settings

log = logging.getLogger(__name__)

# name -> (settings key, compose service, container port, URL path)
BACKENDS = {
    "prometheus": ("PROM_URL", "prometheus", 9090, ""),
    "jaeger": ("JAEGER_URL", "jaeger", 16686, "/jaeger/ui"),
    "opensearch": ("OPENSEARCH_URL", "opensearch", 9200, ""),
}

# Used only when neither config nor Docker gives a URL. OpenSearch has no fixed
# host port in the demo, so it has no default.
DEFAULTS: dict[str, str | None] = {
    "prometheus": "http://127.0.0.1:9090",
    "jaeger": "http://127.0.0.1:8080/jaeger/ui",
    "opensearch": None,
}

# `docker ps` Ports entry such as "0.0.0.0:48275->9200/tcp"; captures the host port.
PORT_MAPPING = r"(?:\d{{1,3}}(?:\.\d{{1,3}}){{3}}|\[::\]):(\d+)->{port}/tcp"

_cache: dict[Settings, dict[str, str | None]] = {}


def _docker_port(project: str, service: str, port: int) -> str | None:
    """Host port Docker publishes for `service`'s container `port`, or None."""
    cmd = [
        "docker",
        "ps",
        "--filter",
        f"label=com.docker.compose.project={project}",
        "--filter",
        f"label=com.docker.compose.service={service}",
        "--format",
        "{{.Ports}}",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("docker ps for %s failed: %s", service, exc)
        return None
    match = re.search(PORT_MAPPING.format(port=port), proc.stdout)
    if proc.returncode != 0 or not match:
        log.warning(
            "no published port %s for %s/%s: %s",
            port,
            project,
            service,
            proc.stderr.strip(),
        )
        return None
    return match.group(1)


def discover_endpoints(settings: Settings | None = None) -> dict[str, str | None]:
    """Return {"prometheus", "jaeger", "opensearch"} URLs. Never raises; unknown ones are None.

    Order per backend: process env / oncall/.env (via Settings), then the port
    Docker publishes for the compose project, then DEFAULTS.
    """
    return _resolve(settings or load_settings())[0]


def resolve_endpoints(settings: Settings | None = None) -> dict[str, str | None]:
    """discover_endpoints(), cached once every URL came from config or Docker."""
    settings = settings or load_settings()
    if settings not in _cache:
        endpoints, complete = _resolve(settings)
        if not complete:
            return endpoints
        _cache[settings] = endpoints
    return dict(_cache[settings])


def _resolve(settings: Settings) -> tuple[dict[str, str | None], bool]:
    endpoints: dict[str, str | None] = {}
    complete = True
    for name, (key, service, port, path) in BACKENDS.items():
        url = getattr(settings, key)
        if not url:
            host_port = _docker_port(settings.COMPOSE_PROJECT_NAME, service, port)
            url = f"http://127.0.0.1:{host_port}{path}" if host_port else None
        if not url:
            complete = False
            url = DEFAULTS[name]
            if url is None:
                log.warning("could not resolve %s endpoint; set %s", name, key)
        endpoints[name] = url.rstrip("/") if url else None
    return endpoints, complete
