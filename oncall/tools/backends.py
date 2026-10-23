"""Telemetry backends: live, recording, and offline (fixtures).

Provides a unified interface for querying Prometheus, Jaeger, and OpenSearch.
Supports live calls via httpx, recording responses to disk, and offline replay
from recorded fixtures.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx

logger = logging.getLogger(__name__)


class BackendError(RuntimeError):
    """Raised when a telemetry backend cannot be reached or returns an error."""


@runtime_checkable
class TelemetryBackend(Protocol):
    """Unified telemetry backend protocol for Prometheus, Jaeger, and OpenSearch."""

    def prom_query(self, promql: str, at: str | None = None) -> dict[str, Any]:
        """Execute an instant PromQL query."""
        ...

    def prom_range(
        self, promql: str, start: str, end: str, step: str = "30s"
    ) -> dict[str, Any]:
        """Execute a range PromQL query."""
        ...

    def jaeger_services(self) -> list[str]:
        """Return list of service names known to Jaeger."""
        ...

    def jaeger_traces(
        self,
        service: str,
        lookback: str = "15m",
        limit: int = 20,
        tags: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return traces matching service and criteria from Jaeger."""
        ...

    def logs_search(
        self,
        service: str | None,
        level: str | None,
        since_min: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search logs in OpenSearch."""
        ...


def make_request_hash(op: str, kwargs: dict[str, Any]) -> str:
    """Generate a deterministic short hash for an operation and its arguments."""
    canonical = json.dumps({"op": op, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class LiveBackend:
    """Live telemetry backend communicating over HTTP using httpx."""

    def __init__(
        self,
        prom_url: str | None = None,
        jaeger_url: str | None = None,
        opensearch_url: str | None = None,
        opensearch_index: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.prom_url = (
            prom_url or os.environ.get("PROM_URL") or "http://localhost:9090"
        ).rstrip("/")
        self.jaeger_url = (
            jaeger_url or os.environ.get("JAEGER_URL") or "http://localhost:16686"
        ).rstrip("/")
        self.opensearch_url = (
            opensearch_url
            or os.environ.get("OPENSEARCH_URL")
            or "http://localhost:9200"
        ).rstrip("/")
        self.opensearch_index = opensearch_index or os.environ.get(
            "OPENSEARCH_LOG_INDEX"
        )
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    def prom_query(self, promql: str, at: str | None = None) -> dict[str, Any]:
        url = f"{self.prom_url}/api/v1/query"
        params: dict[str, str] = {"query": promql}
        if at:
            params["time"] = at

        try:
            with self._client() as client:
                res = client.get(url, params=params)
                if res.status_code != 200:
                    raise BackendError(
                        f"Prometheus query failed (HTTP {res.status_code}): {res.text}"
                    )
                data = res.json()
                if data.get("status") != "success":
                    raise BackendError(f"Prometheus error response: {data}")
                return data
        except httpx.RequestError as exc:
            raise BackendError(f"Prometheus unreachable at {url}: {exc}") from exc

    def prom_range(
        self, promql: str, start: str, end: str, step: str = "30s"
    ) -> dict[str, Any]:
        url = f"{self.prom_url}/api/v1/query_range"
        params = {"query": promql, "start": start, "end": end, "step": step}

        try:
            with self._client() as client:
                res = client.get(url, params=params)
                if res.status_code != 200:
                    raise BackendError(
                        f"Prometheus range query failed (HTTP {res.status_code}): {res.text}"
                    )
                data = res.json()
                if data.get("status") != "success":
                    raise BackendError(f"Prometheus error response: {data}")
                return data
        except httpx.RequestError as exc:
            raise BackendError(f"Prometheus unreachable at {url}: {exc}") from exc

    def jaeger_services(self) -> list[str]:
        # Try direct API first; support proxy path if configured
        endpoints = [
            f"{self.jaeger_url}/api/services",
            f"{self.jaeger_url}/jaeger/ui/api/services",
        ]
        last_exc: Exception | None = None

        with self._client() as client:
            for url in endpoints:
                try:
                    res = client.get(url)
                    if res.status_code == 200:
                        data = res.json()
                        return data.get("data", []) or []
                except httpx.RequestError as exc:
                    last_exc = exc
                    continue

        raise BackendError(
            f"Jaeger unreachable or returned error at {endpoints[0]}: {last_exc}"
        )

    def jaeger_traces(
        self,
        service: str,
        lookback: str = "15m",
        limit: int = 20,
        tags: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        endpoints = [
            f"{self.jaeger_url}/api/traces",
            f"{self.jaeger_url}/jaeger/ui/api/traces",
        ]
        params: dict[str, Any] = {
            "service": service,
            "lookback": lookback,
            "limit": limit,
        }
        if tags:
            # Jaeger accepts JSON string in `tags` parameter or `tag` query params
            params["tags"] = json.dumps(tags)

        last_exc: Exception | None = None
        with self._client() as client:
            for url in endpoints:
                try:
                    res = client.get(url, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        return data.get("data", []) or []
                except httpx.RequestError as exc:
                    last_exc = exc
                    continue

        raise BackendError(f"Jaeger traces query failed at {endpoints[0]}: {last_exc}")

    def _discover_opensearch_index(self, client: httpx.Client) -> str:
        if self.opensearch_index:
            return self.opensearch_index

        try:
            res = client.get(f"{self.opensearch_url}/_cat/indices?format=json")
            if res.status_code == 200:
                indices = res.json()
                for item in indices:
                    idx = item.get("index", "")
                    if "log" in idx or "otel" in idx:
                        self.opensearch_index = idx
                        return idx
        except (httpx.RequestError, json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.debug("Failed to auto-discover OpenSearch index: %s", exc)

        self.opensearch_index = "*"
        return self.opensearch_index

    def logs_search(
        self,
        service: str | None,
        level: str | None,
        since_min: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        try:
            with self._client() as client:
                index = self._discover_opensearch_index(client)
                url = f"{self.opensearch_url}/{index}/_search"

                must_clauses: list[dict[str, Any]] = [
                    {"range": {"@timestamp": {"gte": f"now-{since_min}m"}}}
                ]
                if service:
                    must_clauses.append(
                        {
                            "bool": {
                                "should": [
                                    {"match": {"service_name": service}},
                                    {
                                        "match": {
                                            "resource.attributes.service.name": service
                                        }
                                    },
                                    {"match": {"service": service}},
                                ],
                                "minimum_should_match": 1,
                            }
                        }
                    )
                if level:
                    must_clauses.append(
                        {
                            "bool": {
                                "should": [
                                    {"match": {"severity_text": level}},
                                    {"match": {"level": level}},
                                    {"match": {"severity": level}},
                                ],
                                "minimum_should_match": 1,
                            }
                        }
                    )

                body = {
                    "size": limit,
                    "query": {"bool": {"must": must_clauses}},
                    "sort": [{"@timestamp": {"order": "desc"}}],
                }

                res = client.post(url, json=body)
                if res.status_code != 200:
                    raise BackendError(
                        f"OpenSearch search failed (HTTP {res.status_code}): {res.text}"
                    )

                hits = res.json().get("hits", {}).get("hits", [])
                return [h.get("_source", {}) for h in hits]
        except httpx.RequestError as exc:
            raise BackendError(
                f"OpenSearch unreachable at {self.opensearch_url}: {exc}"
            ) from exc


class RecordingBackend(LiveBackend):
    """Live backend that saves query inputs and outputs into fixture JSON files."""

    def __init__(
        self,
        scenario: str = "baseline",
        fixtures_dir: Path | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.scenario = scenario
        base = Path(
            fixtures_dir
            or os.environ.get("OFFLINE_DIR")
            or Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        )
        self.scenario_dir = base / scenario
        self.scenario_dir.mkdir(parents=True, exist_ok=True)

    def _save(self, op: str, kwargs: dict[str, Any], data: Any) -> None:
        req_hash = make_request_hash(op, kwargs)
        file_path = self.scenario_dir / f"{op}_{req_hash}.json"
        payload = {
            "op": op,
            "kwargs": kwargs,
            "data": data,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True, default=str)

    def prom_query(self, promql: str, at: str | None = None) -> dict[str, Any]:
        data = super().prom_query(promql, at=at)
        self._save("prom_query", {"promql": promql, "at": at}, data)
        return data

    def prom_range(
        self, promql: str, start: str, end: str, step: str = "30s"
    ) -> dict[str, Any]:
        data = super().prom_range(promql, start=start, end=end, step=step)
        self._save(
            "prom_range",
            {"promql": promql, "start": start, "end": end, "step": step},
            data,
        )
        return data

    def jaeger_services(self) -> list[str]:
        data = super().jaeger_services()
        self._save("jaeger_services", {}, data)
        return data

    def jaeger_traces(
        self,
        service: str,
        lookback: str = "15m",
        limit: int = 20,
        tags: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        data = super().jaeger_traces(
            service=service, lookback=lookback, limit=limit, tags=tags
        )
        self._save(
            "jaeger_traces",
            {"service": service, "lookback": lookback, "limit": limit, "tags": tags},
            data,
        )
        return data

    def logs_search(
        self,
        service: str | None,
        level: str | None,
        since_min: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        data = super().logs_search(
            service=service, level=level, since_min=since_min, limit=limit
        )
        self._save(
            "logs_search",
            {
                "service": service,
                "level": level,
                "since_min": since_min,
                "limit": limit,
            },
            data,
        )
        return data


class OfflineBackend:
    """Offline telemetry backend replaying recorded fixture files by request hash."""

    def __init__(
        self,
        scenario: str = "baseline",
        fixtures_dir: Path | str | None = None,
    ) -> None:
        self.scenario = scenario
        base = Path(
            fixtures_dir
            or os.environ.get("OFFLINE_DIR")
            or Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        )
        self.scenario_dir = base / scenario

    def _load(self, op: str, kwargs: dict[str, Any], default: Any) -> Any:
        req_hash = make_request_hash(op, kwargs)
        file_path = self.scenario_dir / f"{op}_{req_hash}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                    return payload.get("data", default)
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Failed to load fixture %s: %s", file_path, exc)
                return default
        return default

    def prom_query(self, promql: str, at: str | None = None) -> dict[str, Any]:
        default = {"status": "success", "data": {"resultType": "vector", "result": []}}
        return self._load("prom_query", {"promql": promql, "at": at}, default)

    def prom_range(
        self, promql: str, start: str, end: str, step: str = "30s"
    ) -> dict[str, Any]:
        default = {"status": "success", "data": {"resultType": "matrix", "result": []}}
        return self._load(
            "prom_range",
            {"promql": promql, "start": start, "end": end, "step": step},
            default,
        )

    def jaeger_services(self) -> list[str]:
        return self._load("jaeger_services", {}, [])

    def jaeger_traces(
        self,
        service: str,
        lookback: str = "15m",
        limit: int = 20,
        tags: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._load(
            "jaeger_traces",
            {"service": service, "lookback": lookback, "limit": limit, "tags": tags},
            [],
        )

    def logs_search(
        self,
        service: str | None,
        level: str | None,
        since_min: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        return self._load(
            "logs_search",
            {
                "service": service,
                "level": level,
                "since_min": since_min,
                "limit": limit,
            },
            [],
        )


def get_backend() -> TelemetryBackend:
    """Return the configured TelemetryBackend instance based on TELEMETRY_BACKEND env var."""
    mode = os.environ.get("TELEMETRY_BACKEND", "live").lower()
    scenario = os.environ.get("OFFLINE_SCENARIO", "baseline")

    if mode == "offline":
        return OfflineBackend(scenario=scenario)
    elif mode in ("record", "recording"):
        return RecordingBackend(scenario=scenario)
    return LiveBackend()
