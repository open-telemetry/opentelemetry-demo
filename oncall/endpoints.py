"""Resolve telemetry backend URLs: env var, then `docker compose port`, then None."""

import logging
import subprocess

from oncall.config import Settings, load_settings

log = logging.getLogger(__name__)

# name -> (settings key, compose service, container port)
BACKENDS = {
    "prometheus": ("PROM_URL", "prometheus", 9090),
    "jaeger": ("JAEGER_URL", "jaeger", 16686),
    "opensearch": ("OPENSEARCH_URL", "opensearch", 9200),
}


def _compose_port(compose_files: list[str], service: str, port: int) -> str | None:
    cmd = ["docker", "compose"]
    for f in compose_files:
        cmd += ["-f", f]
    cmd += ["port", service, str(port)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("docker compose port %s %s failed: %s", service, port, exc)
        return None
    out = proc.stdout.strip()
    if proc.returncode != 0 or ":" not in out:
        log.warning(
            "docker compose port %s %s gave no mapping: %s",
            service,
            port,
            proc.stderr.strip(),
        )
        return None
    host_port = out.splitlines()[0].rsplit(":", 1)[1]
    return f"http://localhost:{host_port}"


def discover_endpoints(settings: Settings | None = None) -> dict[str, str | None]:
    """Return {"prometheus", "jaeger", "opensearch"} URLs. Never raises; unknown ones are None."""
    settings = settings or load_settings()
    endpoints: dict[str, str | None] = {}
    for name, (key, service, port) in BACKENDS.items():
        url = getattr(settings, key) or _compose_port(
            settings.compose_files, service, port
        )
        if url is None:
            log.warning("could not resolve %s endpoint; set %s", name, key)
        endpoints[name] = url
    return endpoints
