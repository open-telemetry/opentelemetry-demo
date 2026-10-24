"""Operator-only pause lease. Never registered as an investigator tool."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

SERVICE = "shipping"


def write_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextmanager
def locked(journal):
    import fcntl
    with Path(str(journal) + ".lock").open("a") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Docker:
    def __init__(self, endpoint=None):
        if not sys.platform.startswith("linux"):
            raise ValueError("Run live practice in Ubuntu WSL with native Docker")
        endpoint = endpoint or self.command(["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], pin=False).strip()
        if os.environ.get("DOCKER_HOST") and not endpoint == os.environ["DOCKER_HOST"]:
            raise ValueError("DOCKER_HOST differs from selected context; select one explicit local engine")
        if not endpoint.startswith("unix:///") or any(c.isspace() for c in endpoint):
            raise ValueError("Practice requires a local Unix Docker socket")
        self.endpoint = endpoint

    def command(self, args, pin=True):
        prefix = ["docker", "--host", self.endpoint] if pin else ["docker"]
        result = subprocess.run(prefix + args, capture_output=True, timeout=20, check=False)
        if result.returncode or len(result.stdout) > 131072:
            raise RuntimeError("Docker command failed; inspect local Docker separately")
        return result.stdout.decode("utf-8")

    def inspect(self, container):
        if len(container) != 64 or any(c not in "0123456789abcdef" for c in container):
            raise ValueError("Expected a full container ID")
        template = '{{json .Id}}|{{json .State.Running}}|{{json .State.Paused}}|{{json .State.Restarting}}|{{json (index .Config.Labels "com.docker.compose.project")}}|{{json (index .Config.Labels "com.docker.compose.service")}}'
        fields = self.command(["inspect", "--format", template, container]).strip().split("|")
        if len(fields) != 6:
            raise ValueError("Unexpected Docker inspection")
        return dict(zip(("id", "running", "paused", "restarting", "project", "service"),
                        map(json.loads, fields)))

    def target(self, project):
        if not project or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in project):
            raise ValueError("Invalid Compose project")
        ids = self.command(["ps", "--all", "--no-trunc", "--quiet",
                            "--filter", "label=com.docker.compose.project=" + project,
                            "--filter", "label=com.docker.compose.service=" + SERVICE]).split()
        if len(ids) != 1:
            raise ValueError("Practice requires exactly one shipping container in the selected project")
        state = self.inspect(ids[0])
        check_identity(state, {"container": ids[0], "project": project, "service": SERVICE})
        if not state["running"] or state["paused"] or state["restarting"]:
            raise ValueError("Practice target must be running, unpaused and not restarting")
        return ids[0]


def check_identity(state, record):
    if (state["id"], state["project"], state["service"]) != (record["container"], record["project"], SERVICE):
        raise ValueError("Practice container identity changed; no mutation performed")


def reset(journal, docker=None):
    journal = Path(journal).resolve()
    with locked(journal):
        record = json.loads(journal.read_text(encoding="utf-8"))
        if record["status"] == "reset_verified":
            return record
        docker = docker or Docker(record["endpoint"])
        if docker.endpoint != record["endpoint"]:
            raise ValueError("Engine changed; no reset performed")
        try:
            state = docker.inspect(record["container"])
            check_identity(state, record)
            if record["status"] in ("pause_requested", "paused", "reset_failed"):
                if state["paused"]:
                    docker.command(["unpause", record["container"]])
                state = docker.inspect(record["container"])
                check_identity(state, record)
                if not state["running"] or state["paused"] or state["restarting"]:
                    raise RuntimeError("Running and unpaused state could not be verified")
                record.update(status="reset_verified", reset_at=time.time(), reset_state=state)
            else:
                record.update(status="cancelled_before_pause", reset_at=time.time())
        except Exception:
            record.update(status="reset_failed", reset_at=time.time())
            write_json(journal, record)
            raise RuntimeError("Practice reset not verified; run the documented reset command") from None
        write_json(journal, record)
        return record


def watchdog(journal):
    journal = Path(journal).resolve()
    with locked(journal):
        record = json.loads(journal.read_text(encoding="utf-8"))
        Docker(record["endpoint"])
        Path(str(journal) + ".ready").write_text("ready", encoding="ascii")
    while True:
        with locked(journal):
            record = json.loads(journal.read_text(encoding="utf-8"))
        if record["status"] in ("reset_verified", "cancelled_before_pause"):
            return 0
        if time.time() >= record["deadline"]:
            for _ in range(12):
                try:
                    reset(journal)
                    return 0
                except Exception:
                    time.sleep(5)
            return 1
        time.sleep(min(1, max(0, record["deadline"] - time.time())))


class Practice:
    def __init__(self, journal, project, seconds=240, docker=None):
        if type(seconds) is not int or not 60 <= seconds <= 600:
            raise ValueError("Practice duration must be 60..600 seconds")
        self.journal = Path(journal).resolve()
        self.project, self.seconds = project, seconds
        self.docker = docker or Docker()
        self.container = self.docker.target(project)
        self.child = None

    def start(self):
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("x", encoding="utf-8") as stream:
            json.dump({"container": self.container, "project": self.project, "service": SERVICE,
                       "endpoint": self.docker.endpoint, "status": "armed",
                       "created_at": time.time(), "deadline": time.time() + self.seconds}, stream)
        try:
            self.child = subprocess.Popen(
                [sys.executable, "-B", "-m", "incident_tools.eyes_acceptance", "_watchdog", "--journal", str(self.journal)],
                cwd=Path(__file__).resolve().parents[2],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True, close_fds=True)
            ready = Path(str(self.journal) + ".ready")
            until = time.monotonic() + 8
            while not ready.exists():
                if self.child.poll() is not None or time.monotonic() >= until:
                    raise RuntimeError("Reset watchdog did not become ready; practice not started")
                time.sleep(0.05)
            lease_name = hashlib.sha256((self.docker.endpoint + self.container).encode()).hexdigest()
            lease = Path(tempfile.gettempdir()) / ("eyes-practice-" + lease_name)
            with locked(lease), locked(self.journal):
                record = json.loads(self.journal.read_text(encoding="utf-8"))
                state = self.docker.inspect(self.container)
                check_identity(state, record)
                if (record["status"] != "armed" or time.time() >= record["deadline"]
                        or self.child.poll() is not None or state["paused"]
                        or not state["running"] or state["restarting"]):
                    raise RuntimeError("Practice lease or target no longer ready")
                record["status"] = "pause_requested"
                write_json(self.journal, record)
                self.docker.command(["pause", self.container])
                state = self.docker.inspect(self.container)
                check_identity(state, record)
                if not state["paused"]:
                    raise RuntimeError("Pause was not verified")
                record.update(status="paused", paused_at=time.time())
                write_json(self.journal, record)
        except BaseException:
            if self.journal.exists():
                self.reset()
            raise

    def reset(self):
        return reset(self.journal, self.docker)
