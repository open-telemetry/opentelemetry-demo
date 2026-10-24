"""One read-only request per backend, plus the demo's containers from Docker.

Run with: python -m tools.check_backends
Each backend is reported as reachable / unreachable / error, with the URL used.
  reachable   = answered with a well-formed, healthy response
  unreachable = no answer (connection refused, timeout, docker not running)
  error       = answered, but with something wrong (HTTP error, bad body, red status)
Exit code is 0 only if every check is reachable.
"""
import subprocess
import sys
from dataclasses import dataclass

import requests

from tools.endpoints import compose_project, get_endpoints, load_settings

TIMEOUT_SECONDS = 10


@dataclass
class Result:
    name: str
    state: str  # "reachable", "unreachable" or "error"
    target: str  # the URL (or docker command) that was used
    detail: str


def fetch_json(url: str) -> tuple[dict | None, tuple[str, str] | None]:
    """GET a URL. Returns (json, None) on success or (None, (state, detail)) on failure."""
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as exc:
        return None, ("unreachable", f"{type(exc).__name__}: {str(exc)[:120]}")
    if not response.ok:
        return None, ("error", f"HTTP {response.status_code}")
    try:
        return response.json(), None
    except ValueError:
        return None, ("error", "response was not JSON")


def check_prometheus(base_url: str) -> Result:
    url = f"{base_url}/api/v1/status/buildinfo"
    data, problem = fetch_json(url)
    if problem:
        return Result("prometheus", problem[0], url, problem[1])
    if data.get("status") != "success":
        return Result("prometheus", "error", url, f"status={data.get('status')!r}")
    return Result("prometheus", "reachable", url, f"version {data['data'].get('version')}")


def check_jaeger(base_url: str) -> Result:
    url = f"{base_url}/api/v3/services"
    data, problem = fetch_json(url)
    if problem:
        return Result("jaeger", problem[0], url, problem[1])
    if not isinstance(data.get("services"), list):
        return Result("jaeger", "error", url, "response has no 'services' list")
    return Result("jaeger", "reachable", url, f"{len(data['services'])} services listed")


def check_opensearch(base_url: str | None, discovery_error: str | None) -> Result:
    if base_url is None:
        return Result("opensearch", "error", "(no URL)", f"port discovery failed: {discovery_error}")
    url = f"{base_url}/_cluster/health"
    data, problem = fetch_json(url)
    if problem:
        return Result("opensearch", problem[0], url, problem[1])
    status = data.get("status")
    if status in ("green", "yellow"):
        return Result("opensearch", "reachable", url, f"cluster status {status}")
    return Result("opensearch", "error", url, f"cluster status {status!r}")


def check_docker(project: str) -> Result:
    """List every container (running or not) that belongs to the compose project."""
    command = ["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={project}",
               "--format", "{{.Names}}\t{{.Status}}"]
    target = " ".join(command)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Result("docker", "unreachable", target, f"{type(exc).__name__}: {exc}")
    if result.returncode != 0:
        return Result("docker", "error", target, result.stderr.strip() or f"exit code {result.returncode}")
    rows = [line.split("\t", 1) for line in result.stdout.splitlines() if line.strip()]
    if not rows:
        return Result("docker", "error", target, f"no containers carry project label {project!r}")
    # Anything not plainly "Up", or reporting unhealthy, is called out by name.
    bad = [f"{name} ({status})" for name, status in rows
           if not status.startswith("Up") or "unhealthy" in status]
    if bad:
        return Result("docker", "error", target, f"{len(rows)} containers, not OK: " + "; ".join(bad))
    return Result("docker", "reachable", target, f"{len(rows)} containers, all Up")


def main() -> int:
    settings = load_settings()
    endpoints = get_endpoints(settings)
    project = compose_project(settings)

    results = [
        check_prometheus(endpoints["prometheus"].url),
        check_jaeger(endpoints["jaeger"].url),
        check_opensearch(endpoints["opensearch"].url, endpoints["opensearch"].error),
        check_docker(project),
    ]
    print(f"compose project: {project}")
    for r in results:
        print(f"[{r.state.upper():11}] {r.name:10} {r.target}\n{'':14}{r.detail}")
    return 0 if all(r.state == "reachable" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
