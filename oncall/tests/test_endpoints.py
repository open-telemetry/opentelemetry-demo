import subprocess
from unittest import mock

import pytest

from oncall import endpoints
from oncall.config import Settings
from oncall.endpoints import DEFAULTS, discover_endpoints, resolve_endpoints

PORTS = {
    "prometheus": "0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp",
    "jaeger": "0.0.0.0:48282->4317/tcp, 0.0.0.0:48281->16686/tcp",
    "opensearch": "0.0.0.0:48275->9200/tcp, [::]:48275->9200/tcp",
}


@pytest.fixture(autouse=True)
def clear_cache():
    endpoints._cache.clear()
    yield
    endpoints._cache.clear()


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=""
    )


def _fake_docker_ps(cmd, **kwargs):
    service = next(a for a in cmd if a.startswith("label=com.docker.compose.service="))
    return _completed(PORTS[service.rsplit("=", 1)[1]] + "\n")


def test_env_values_win_without_calling_docker():
    settings = Settings(
        PROM_URL="http://p:1", JAEGER_URL="http://j:2/", OPENSEARCH_URL="http://o:3"
    )
    with mock.patch("oncall.endpoints.subprocess.run") as run:
        result = discover_endpoints(settings)
    run.assert_not_called()
    assert result == {
        "prometheus": "http://p:1",
        "jaeger": "http://j:2",
        "opensearch": "http://o:3",
    }


def test_published_ports_of_the_compose_project_are_used():
    with mock.patch(
        "oncall.endpoints.subprocess.run", side_effect=_fake_docker_ps
    ) as run:
        result = discover_endpoints(Settings(COMPOSE_PROJECT_NAME="demo"))
    assert result == {
        "prometheus": "http://127.0.0.1:9090",
        "jaeger": "http://127.0.0.1:48281/jaeger/ui",
        "opensearch": "http://127.0.0.1:48275",
    }
    args = run.call_args_list[1].args[0]
    assert args[:2] == ["docker", "ps"]
    assert "label=com.docker.compose.project=demo" in args
    assert "label=com.docker.compose.service=jaeger" in args


@pytest.mark.parametrize(
    "docker",
    [
        {"side_effect": FileNotFoundError("docker")},
        {"return_value": _completed("", returncode=1)},
        {"side_effect": subprocess.TimeoutExpired(cmd="docker", timeout=5)},
    ],
    ids=["not-installed", "daemon-down", "timeout"],
)
def test_docker_unavailable_falls_back_to_defaults(docker):
    with mock.patch("oncall.endpoints.subprocess.run", **docker):
        result = discover_endpoints(Settings())
    assert result == DEFAULTS
    assert result["opensearch"] is None


def test_resolve_caches_only_a_complete_discovery():
    with mock.patch(
        "oncall.endpoints.subprocess.run", return_value=_completed("", returncode=1)
    ) as run:
        resolve_endpoints(Settings())
        resolve_endpoints(Settings())
    assert run.call_count == 6
    with mock.patch(
        "oncall.endpoints.subprocess.run", side_effect=_fake_docker_ps
    ) as run:
        first = resolve_endpoints(Settings())
        second = resolve_endpoints(Settings())
    assert run.call_count == 3
    assert first == second
    assert first["opensearch"] == "http://127.0.0.1:48275"
