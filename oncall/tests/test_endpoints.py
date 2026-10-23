import subprocess
from unittest import mock

from oncall.config import Settings
from oncall.endpoints import discover_endpoints


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=""
    )


def test_env_values_win_without_calling_docker():
    settings = Settings(
        PROM_URL="http://p:1", JAEGER_URL="http://j:2", OPENSEARCH_URL="http://o:3"
    )
    with mock.patch("oncall.endpoints.subprocess.run") as run:
        result = discover_endpoints(settings)
    run.assert_not_called()
    assert result == {
        "prometheus": "http://p:1",
        "jaeger": "http://j:2",
        "opensearch": "http://o:3",
    }


def test_compose_port_mapping_is_used():
    with mock.patch(
        "oncall.endpoints.subprocess.run", return_value=_completed("0.0.0.0:32768\n")
    ) as run:
        result = discover_endpoints(Settings())
    assert result["jaeger"] == "http://localhost:32768"
    args = run.call_args_list[1].args[0]
    assert args == [
        "docker",
        "compose",
        "-f",
        "compose.yaml",
        "-f",
        "compose.observability.yaml",
        "port",
        "jaeger",
        "16686",
    ]


def test_docker_not_installed_returns_none():
    with mock.patch(
        "oncall.endpoints.subprocess.run", side_effect=FileNotFoundError("docker")
    ):
        result = discover_endpoints(Settings())
    assert result == {"prometheus": None, "jaeger": None, "opensearch": None}


def test_docker_daemon_down_returns_none():
    with mock.patch(
        "oncall.endpoints.subprocess.run", return_value=_completed("", returncode=1)
    ):
        result = discover_endpoints(Settings())
    assert result == {"prometheus": None, "jaeger": None, "opensearch": None}


def test_timeout_returns_none():
    timeout = subprocess.TimeoutExpired(cmd="docker", timeout=5)
    with mock.patch("oncall.endpoints.subprocess.run", side_effect=timeout):
        result = discover_endpoints(Settings())
    assert result["prometheus"] is None
