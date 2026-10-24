"""Container faults: `docker stop` / `docker start` on three allowlisted demo containers.

Every command is a fixed argument list run without a shell. Containers are never removed,
and volumes, images and compose projects are never touched.
"""
import json
import os
import re
import subprocess
import time
from urllib.parse import urlparse

from dev.faultctl.catalog import ALLOWED_CONTAINERS, COMPOSE_PROJECT, Incident
from dev.faultctl.outcome import Outcome, Refused, Result

PROJECT_LABEL = "com.docker.compose.project"
INSPECT_TIMEOUT = 20
STOP_START_TIMEOUT = 60
HEALTH_WAIT_SECONDS = 60
HEALTH_POLL_SECONDS = 2
LOCAL_SCHEMES = {"unix", "npipe", "fd"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
CONTAINER_ID = re.compile(r"^[0-9a-f]{12,64}$")  # ids printed by `docker ps -q`


class DockerError(Exception):
    pass


class DockerTimeout(Exception):
    pass


def is_local_host(host: str) -> bool:
    """True if a Docker daemon address (DOCKER_HOST style) points at this machine."""
    parsed = urlparse(host)
    if parsed.scheme in LOCAL_SCHEMES:
        return True
    return parsed.scheme == "tcp" and parsed.hostname in LOOPBACK_HOSTS


class DockerCli:
    """Runs the docker CLI. Tests pass a fake `runner`, or replace this class entirely."""

    def __init__(self, runner=subprocess.run):
        self._runner = runner

    def _run(self, args: list[str], timeout: int):
        try:
            return self._runner(["docker", *args], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise DockerTimeout(f"docker {args[0]} timed out after {timeout}s") from exc
        except OSError as exc:
            raise DockerError(f"cannot run docker: {exc}") from exc

    @staticmethod
    def _require_allowed(name: str) -> None:
        if name not in ALLOWED_CONTAINERS:
            raise Refused(f"container {name!r} is not on the allowlist")

    def daemon_host(self) -> str:
        """Address of the Docker daemon in use: DOCKER_HOST, else the current docker context."""
        if os.environ.get("DOCKER_HOST"):
            return os.environ["DOCKER_HOST"]
        proc = self._run(["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], INSPECT_TIMEOUT)
        return proc.stdout.strip() if proc.returncode == 0 else ""

    def inspect(self, name: str) -> dict | None:
        """`docker inspect` of an allowlisted container; None if it does not exist."""
        self._require_allowed(name)
        proc = self._run(["inspect", "--type", "container", name], INSPECT_TIMEOUT)
        if proc.returncode != 0:
            if "no such" in proc.stderr.lower():
                return None
            raise DockerError(f"docker inspect failed: {proc.stderr.strip()[:200]}")
        try:
            return json.loads(proc.stdout)[0]
        except (ValueError, IndexError) as exc:
            raise DockerError("docker inspect output was not understood") from exc

    def stop(self, name: str) -> None:
        self._require_allowed(name)
        proc = self._run(["stop", name], STOP_START_TIMEOUT)
        if proc.returncode != 0:
            raise DockerError(f"docker stop failed: {proc.stderr.strip()[:200]}")

    def start(self, name: str) -> None:
        self._require_allowed(name)
        proc = self._run(["start", name], STOP_START_TIMEOUT)
        if proc.returncode != 0:
            raise DockerError(f"docker start failed: {proc.stderr.strip()[:200]}")

    def project_containers(self, project: str) -> list[dict]:
        """`docker inspect` of every container (running or not) of one compose project."""
        proc = self._run(["ps", "-a", "-q", "--filter", f"label={PROJECT_LABEL}={project}"], INSPECT_TIMEOUT)
        if proc.returncode != 0:
            raise DockerError(f"docker ps failed: {proc.stderr.strip()[:200]}")
        ids = [line for line in proc.stdout.split() if CONTAINER_ID.match(line)]
        if not ids:
            return []
        proc = self._run(["inspect", "--type", "container", *ids], INSPECT_TIMEOUT)
        if proc.returncode != 0:
            raise DockerError(f"docker inspect failed: {proc.stderr.strip()[:200]}")
        try:
            return json.loads(proc.stdout)
        except ValueError as exc:
            raise DockerError("docker inspect output was not understood") from exc


def health_of(info: dict) -> str | None:
    """The container's healthcheck status, or None if it has no healthcheck."""
    return (info.get("State", {}).get("Health") or {}).get("Status")


class ContainerOps:
    def __init__(self, docker, project: str = COMPOSE_PROJECT, sleep=time.sleep):
        self.docker = docker
        self.project = project
        self.sleep = sleep

    def _inspect_checked(self, name: str) -> dict:
        """Inspect a container after the safety checks: local daemon, correct compose project."""
        host = self.docker.daemon_host()
        if not is_local_host(host):
            raise Refused(f"docker daemon {host or '(unknown)'!r} is not local")
        info = self.docker.inspect(name)
        if info is None:
            raise DockerError(f"container {name} does not exist")
        labels = info.get("Config", {}).get("Labels") or {}
        if labels.get(PROJECT_LABEL) != self.project:
            raise Refused(f"container {name} is not in compose project {self.project!r}")
        return info

    def _preflight(self, name: str):
        """Returns (info, None) or (None, failure Result). Refusals propagate as Refused."""
        try:
            return self._inspect_checked(name), None
        except DockerTimeout as exc:
            return None, Result(Outcome.TIMED_OUT, [str(exc)])
        except DockerError as exc:
            return None, Result(Outcome.FAILED, [str(exc)])

    def stop(self, incident: Incident, dry_run: bool) -> Result:
        name = incident.target
        info, failure = self._preflight(name)
        if failure:
            return failure
        status = info["State"]["Status"]
        if not info["State"]["Running"]:
            note = f"container {name} is already {status}; nothing to stop"
            return Result(Outcome.DRY_RUN if dry_run else Outcome.VERIFIED, [note])
        plan = f"container {name}: {status} -> stopped (docker stop {name})"
        if dry_run:
            return Result(Outcome.DRY_RUN, [f"plan: {plan}"])
        try:
            self.docker.stop(name)
        except DockerTimeout:
            return Result(Outcome.TIMED_OUT, [plan, "docker stop timed out and was NOT retried; check with `status`"])
        except DockerError as exc:
            return Result(Outcome.FAILED, [plan, str(exc)])
        try:
            after = self.docker.inspect(name)
        except (DockerError, DockerTimeout) as exc:
            return Result(Outcome.UNVERIFIED, [plan, f"stop returned OK but the re-inspect failed: {exc}"])
        if after and not after["State"]["Running"]:
            return Result(Outcome.VERIFIED, [plan, f"docker inspect: state is now {after['State']['Status']}"])
        return Result(Outcome.FAILED, [plan, "docker stop returned OK but the container is still running"])

    def start(self, incident: Incident, dry_run: bool) -> Result:
        name = incident.target
        info, failure = self._preflight(name)
        if failure:
            return failure
        status = info["State"]["Status"]
        if info["State"]["Running"] and health_of(info) in (None, "healthy"):
            note = f"container {name} is already running; nothing to start"
            return Result(Outcome.DRY_RUN if dry_run else Outcome.VERIFIED, [note])
        plan = f"container {name}: {status} -> running and healthy (docker start {name})"
        if dry_run:
            return Result(Outcome.DRY_RUN, [f"plan: {plan}"])
        if not info["State"]["Running"]:
            try:
                self.docker.start(name)
            except DockerTimeout:
                return Result(Outcome.TIMED_OUT, [plan, "docker start timed out and was NOT retried; check with `status`"])
            except DockerError as exc:
                return Result(Outcome.FAILED, [plan, str(exc)])
        return self._wait_until_healthy(name, plan)

    def _wait_until_healthy(self, name: str, plan: str) -> Result:
        """Poll `docker inspect` until the container runs (and passes its healthcheck, if any)."""
        last = None
        for _ in range(HEALTH_WAIT_SECONDS // HEALTH_POLL_SECONDS + 1):
            try:
                last = self.docker.inspect(name)
            except (DockerError, DockerTimeout) as exc:
                return Result(Outcome.UNVERIFIED, [plan, f"start returned OK but the re-inspect failed: {exc}"])
            if last and last["State"]["Running"] and health_of(last) in (None, "healthy"):
                health = health_of(last) or "no healthcheck"
                return Result(Outcome.VERIFIED, [plan, f"docker inspect: running, {health}"])
            self.sleep(HEALTH_POLL_SECONDS)
        if last and last["State"]["Running"]:
            return Result(Outcome.UNVERIFIED, [plan, f"running, but health is {health_of(last)!r} "
                                                     f"after {HEALTH_WAIT_SECONDS}s"])
        return Result(Outcome.FAILED, [plan, "docker start returned OK but the container is not running"])
