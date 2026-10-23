from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
import os
import threading
import time
from typing import Any

import docker

logger = logging.getLogger("action-api.docker")

COMPOSE_PROJECT_NAME = os.environ.get("COMPOSE_PROJECT_NAME", "opentelemetry-demo")


class DockerManager:
    def __init__(self) -> None:
        self._client: docker.DockerClient | None = None
        self._stats_cache: dict[str, dict[str, Any]] = {}
        self._stats_lock = threading.Lock()
        self._events_buffer: deque[dict[str, Any]] = deque(maxlen=2000)
        self._events_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._init_client()
        self._start_background_workers()

    def _init_client(self) -> None:
        try:
            self._client = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not connect to Docker socket: {e}")
            self._client = None

    def get_client(self) -> docker.DockerClient | None:
        if self._client is None:
            self._init_client()
        return self._client

    def _start_background_workers(self) -> None:
        t_events = threading.Thread(target=self._watch_docker_events, daemon=True, name="docker-events-watcher")
        t_events.start()
        t_stats = threading.Thread(target=self._refresh_stats_loop, daemon=True, name="docker-stats-watcher")
        t_stats.start()

    def _watch_docker_events(self) -> None:
        client = self.get_client()
        if not client:
            return

        now = int(time.time())
        try:
            historical = client.events(
                since=now - 3600,
                until=now,
                decode=True,
                filters={"type": "container", "event": ["start", "die", "oom", "restart", "kill", "stop"]},
            )
            for ev in historical:
                self._record_raw_docker_event(ev)
        except Exception as e:
            logger.debug(f"Error fetching historical events: {e}")

        while not self._stop_event.is_set():
            try:
                client = self.get_client()
                if not client:
                    time.sleep(5)
                    continue
                for ev in client.events(
                    decode=True,
                    filters={"type": "container", "event": ["start", "die", "oom", "restart", "kill", "stop"]},
                ):
                    if self._stop_event.is_set():
                        break
                    self._record_raw_docker_event(ev)
            except Exception as e:
                logger.debug(f"Docker event listener error: {e}")
                time.sleep(3)

    def _record_raw_docker_event(self, ev: dict[str, Any]) -> None:
        ev_time = ev.get("time", int(time.time()))
        dt_str = datetime.fromtimestamp(ev_time, tz=timezone.utc).isoformat()
        actor = ev.get("Actor", {})
        attrs = actor.get("Attributes", {})
        container_name = attrs.get("name", actor.get("ID", "")[:12])
        status = ev.get("status") or ev.get("Action", "unknown")

        record = {
            "timestamp": dt_str,
            "epoch": ev_time,
            "source": "docker",
            "type": status,
            "service": container_name,
            "details": {
                "id": actor.get("ID", "")[:12],
                "image": attrs.get("image", ""),
                "exit_code": attrs.get("exitCode"),
            },
        }
        with self._events_lock:
            self._events_buffer.append(record)

    def record_action_event(self, action: str, service: str, details: dict[str, Any]) -> None:
        now_ts = int(time.time())
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch": now_ts,
            "source": "action-api",
            "type": action,
            "service": service,
            "details": details,
        }
        with self._events_lock:
            self._events_buffer.append(record)

    def get_events(self, since_minutes: int = 60) -> list[dict[str, Any]]:
        threshold = int(time.time()) - (since_minutes * 60)
        with self._events_lock:
            return [ev for ev in self._events_buffer if ev.get("epoch", 0) >= threshold]

    def _sample_container_stat(self, container: Any) -> tuple[str, dict[str, Any]]:
        name = container.name
        try:
            st = container.stats(stream=False)
            cpu_delta = (
                st.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                - st.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            )
            system_cpu_delta = (
                st.get("cpu_stats", {}).get("system_cpu_usage", 0)
                - st.get("precpu_stats", {}).get("system_cpu_usage", 0)
            )
            num_cpus = st.get("cpu_stats", {}).get("online_cpus", 1) or 1
            cpu_percent = 0.0
            if system_cpu_delta > 0 and cpu_delta > 0:
                cpu_percent = round((cpu_delta / system_cpu_delta) * num_cpus * 100.0, 2)

            mem_usage = st.get("memory_stats", {}).get("usage", 0)
            mem_limit = st.get("memory_stats", {}).get("limit", 0)

            return name, {
                "cpu_percent": cpu_percent,
                "memory_usage_bytes": mem_usage,
                "memory_limit_bytes": mem_limit,
            }
        except Exception:
            return name, {"cpu_percent": 0.0, "memory_usage_bytes": 0, "memory_limit_bytes": 0}

    def _refresh_stats_loop(self) -> None:
        while not self._stop_event.is_set():
            client = self.get_client()
            if client:
                try:
                    containers = client.containers.list(filters={"status": "running"})
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        results = list(executor.map(self._sample_container_stat, containers))
                    with self._stats_lock:
                        for name, stats in results:
                            self._stats_cache[name] = stats
                except Exception as e:
                    logger.debug(f"Stats refresh loop error: {e}")
            self._stop_event.wait(20)

    def _format_container(self, c: Any) -> dict[str, Any]:
        attrs = c.attrs or {}
        state = attrs.get("State", {})
        health = state.get("Health", {}).get("Status", "none")
        name = c.name

        with self._stats_lock:
            stats = self._stats_cache.get(name, {})

        return {
            "name": name,
            "state": c.status,
            "status": state.get("Status", c.status),
            "health": health,
            "restart_count": attrs.get("RestartCount", 0),
            "oom_killed": state.get("OOMKilled", False),
            "exit_code": state.get("ExitCode", 0),
            "started_at": state.get("StartedAt", ""),
            "image_id": attrs.get("Image", ""),
            "created": attrs.get("Created", ""),
            "cpu_percent": stats.get("cpu_percent", 0.0),
            "memory_usage_bytes": stats.get("memory_usage_bytes", 0),
            "memory_limit_bytes": stats.get("memory_limit_bytes", 0),
        }

    def get_containers(self) -> list[dict[str, Any]]:
        client = self.get_client()
        if not client:
            return []
        try:
            containers = client.containers.list(all=True)
            return [self._format_container(c) for c in containers]
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            return []

    def get_container(self, name: str) -> dict[str, Any] | None:
        client = self.get_client()
        if not client:
            return None
        try:
            c = client.containers.get(name)
            return self._format_container(c)
        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Failed to get container {name}: {e}")
            return None

    def restart_container(self, name: str, timeout: int = 10) -> tuple[bool, str]:
        client = self.get_client()
        if not client:
            return False, "Docker daemon not reachable"
        try:
            c = client.containers.get(name)
            c.restart(timeout=timeout)
            self.record_action_event("restart_service", name, {"timeout": timeout})
            return True, f"Container '{name}' restarted successfully"
        except docker.errors.NotFound:
            return False, f"Container '{name}' not found"
        except Exception as e:
            return False, f"Docker restart failed: {e}"


docker_manager = DockerManager()
