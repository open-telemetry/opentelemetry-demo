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
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx

from oncall.config import load_settings
from oncall.endpoints import resolve_endpoints
from oncall.models import FLAG_PATTERN, FLAG_REDACTED, scrub_flags
from oncall.safety.exclusions import (
    EXCLUDED_SERVICES,
    FIXTURE_SCRUB,
    PROMQL_EXCLUDE,
    is_excluded,
    is_excluded_span,
)

logger = logging.getLogger(__name__)

DEFAULT_LOG_INDEX = "otel-logs-*"
# Keyword sub-field: a term query on the analysed text field misses names with "-".
LOG_SERVICE_FIELD = "resource.service.name.keyword"
# Lowest OTel severity number per level (WARN 13-16, ERROR 17-20, FATAL 21-24).
LOG_LEVEL_MIN = {"info": 9, "warn": 13, "error": 17}

RFC3339 = "%Y-%m-%dT%H:%M:%SZ"
OTLP_STATUS = {
    2: "ERROR",
    "STATUS_CODE_ERROR": "ERROR",
    1: "OK",
    "STATUS_CODE_OK": "OK",
}


def _lookback_minutes(lookback: str) -> int:
    """'15m' -> 15, '2h' -> 120, '30' -> 30."""
    match = re.fullmatch(r"(\d+)([mh]?)", lookback.strip())
    if not match:
        return 15
    value = int(match.group(1))
    return value * 60 if match.group(2) == "h" else value


def _otlp_value(value: dict[str, Any]) -> Any:
    """Decode an OTLP JSON AnyValue; intValue arrives as a string."""
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "arrayValue" in value:
        return [_otlp_value(v) for v in value["arrayValue"].get("values", [])]
    if "kvlistValue" in value:
        return _otlp_attrs(value["kvlistValue"].get("values", []))
    return None


def _otlp_attrs(items: list[dict[str, Any]]) -> dict[str, Any]:
    """OTLP key/value list -> flat dict, without feature-flag keys."""
    return {
        item["key"]: _otlp_value(item.get("value") or {})
        for item in items
        if item.get("key") and not FLAG_PATTERN.search(item["key"])
    }


def otlp_to_traces(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Jaeger v3 OTLP JSON -> [{"traceId", "spans": [...]}] in first-seen order.

    Each span: spanId, parentSpanId, name, service, serviceVersion, kind,
    startTimeUnixNano, status {code: ERROR|OK|UNSET, message}, attributes,
    events [{name, attributes}]. Spans of excluded services and flag spans are
    dropped, as are feature-flag attributes and events.
    """
    traces: dict[str, list[dict[str, Any]]] = {}
    for resource_spans in (doc.get("result") or {}).get("resourceSpans", []):
        resource = _otlp_attrs(
            (resource_spans.get("resource") or {}).get("attributes", [])
        )
        service = str(resource.get("service.name") or "unattributed")
        if is_excluded(service):
            continue
        for scope_spans in resource_spans.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                name = str(span.get("name") or "<unnamed>")
                if is_excluded_span(name):
                    continue
                status = span.get("status") or {}
                traces.setdefault(span.get("traceId", ""), []).append(
                    {
                        "spanId": span.get("spanId", ""),
                        "parentSpanId": span.get("parentSpanId") or None,
                        "name": name,
                        "service": service,
                        "serviceVersion": resource.get("service.version"),
                        "kind": span.get("kind"),
                        "startTimeUnixNano": span.get("startTimeUnixNano"),
                        "status": {
                            "code": OTLP_STATUS.get(status.get("code"), "UNSET"),
                            "message": status.get("message") or "",
                        },
                        "attributes": _otlp_attrs(span.get("attributes", [])),
                        "events": [
                            {
                                "name": event.get("name", ""),
                                "attributes": _otlp_attrs(event.get("attributes", [])),
                            }
                            for event in span.get("events", [])
                            if not FLAG_PATTERN.search(event.get("name", ""))
                        ],
                    }
                )
    return [{"traceId": tid, "spans": spans} for tid, spans in traces.items()]


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


# A PromQL range selector window such as "[5m]".
PROMQL_WINDOW = re.compile(r"\[\d+[smh]\]")
LOG_KEEP_ATTRIBUTES = ("exception.message", "exception.type")
SPAN_KEEP_ATTRIBUTES = (
    "http.response.status_code",
    "http.status_code",
    "rpc.method",
    "exception.message",
    "error.message",
    "grpc.error_message",
    "error.type",
)
FIXTURE_TEXT_CHARS = 400


def fixture_key(op: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """The arguments a recorded call is filed under, so replay matches the agent's calls.

    PromQL: window and exclusion matcher replaced by placeholders, the instant
    reduced to now vs baseline. Traces: service + filter. Logs: service + level.
    Limits and look-back windows are ignored (replay truncates to the limit).
    """
    if op == "prom_query":
        promql = kwargs["promql"].replace(PROMQL_EXCLUDE, "{exclude}")
        return {
            "promql": PROMQL_WINDOW.sub("[{window}]", promql),
            "baseline": kwargs.get("at") is not None,
        }
    if op == "jaeger_traces":
        return {"service": kwargs["service"], "tags": kwargs.get("tags")}
    if op == "logs_search":
        return {"service": kwargs.get("service"), "level": kwargs.get("level")}
    return kwargs


def _trim_log(doc: dict[str, Any]) -> dict[str, Any]:
    resource = doc.get("resource") or {}
    attributes = doc.get("attributes") or {}
    body = doc.get("body")
    return {
        **{
            k: doc[k]
            for k in ("@timestamp", "severity", "traceId", "spanId")
            if k in doc
        },
        "body": body[:FIXTURE_TEXT_CHARS] if isinstance(body, str) else body,
        "resource": {
            k: v
            for k, v in resource.items()
            if k in ("service.name", "service.version")
        },
        "attributes": {
            k: str(v)[:FIXTURE_TEXT_CHARS]
            for k, v in attributes.items()
            if k in LOG_KEEP_ATTRIBUTES
        },
    }


def _trim_span(span: dict[str, Any]) -> dict[str, Any]:
    return {
        **span,
        "attributes": {
            k: v
            for k, v in span.get("attributes", {}).items()
            if k in SPAN_KEEP_ATTRIBUTES
        },
        "events": [
            {
                "name": "exception",
                "attributes": {
                    "exception.message": str(e["attributes"]["exception.message"])[
                        :FIXTURE_TEXT_CHARS
                    ]
                },
            }
            for e in span.get("events", [])
            if (e.get("attributes") or {}).get("exception.message")
        ],
    }


def fixture_data(op: str, data: Any) -> Any:
    """Shrink a recorded response to the fields the tools read."""
    if op == "logs_search":
        return [_trim_log(d) for d in data]
    if op == "jaeger_traces":
        return [
            {**t, "spans": [_trim_span(s) for s in t.get("spans", [])]} for t in data
        ]
    return data


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
        settings = load_settings()
        endpoints = (
            {}
            if prom_url and jaeger_url and opensearch_url
            else resolve_endpoints(settings)
        )
        self.prom_url = (prom_url or endpoints["prometheus"] or "").rstrip("/")
        self.jaeger_url = (jaeger_url or endpoints["jaeger"] or "").rstrip("/")
        self.opensearch_url = (opensearch_url or endpoints["opensearch"] or "").rstrip(
            "/"
        )
        self.opensearch_index = opensearch_index or settings.OPENSEARCH_LOG_INDEX
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

    def _jaeger_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.jaeger_url}/api/v3/{path}"
        try:
            with self._client() as client:
                res = client.get(url, params=params)
        except httpx.RequestError as exc:
            raise BackendError(f"Jaeger unreachable at {url}: {exc}") from exc
        try:
            data = res.json()
        except ValueError as exc:
            raise BackendError(
                f"Jaeger returned non-JSON (HTTP {res.status_code}) at {url}; "
                "JAEGER_URL must be the UI base, e.g. http://127.0.0.1:8080/jaeger/ui"
            ) from exc
        error = data.get("error") if isinstance(data, dict) else None
        # Jaeger v3 answers an empty search with 404 "No traces found".
        if res.status_code == 404 and error and "no traces" in str(error).lower():
            return {}
        if res.status_code != 200 or error:
            raise BackendError(f"Jaeger query failed (HTTP {res.status_code}): {error}")
        return data

    def jaeger_services(self) -> list[str]:
        services = self._jaeger_get("services").get("services") or []
        return [s for s in services if not is_excluded(s)]

    def jaeger_traces(
        self,
        service: str,
        lookback: str = "15m",
        limit: int = 20,
        tags: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        end = datetime.now(UTC)
        start = end - timedelta(minutes=_lookback_minutes(lookback))
        params: dict[str, Any] = {
            "query.service_name": service,
            "query.start_time_min": start.strftime(RFC3339),
            "query.start_time_max": end.strftime(RFC3339),
            "query.num_traces": limit,
        }
        if tags:
            params["query.attributes"] = json.dumps(tags)
        return otlp_to_traces(self._jaeger_get("traces", params))

    def logs_search(
        self,
        service: str | None,
        level: str | None,
        since_min: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        if not self.opensearch_url:
            raise BackendError("OpenSearch endpoint not found; set OPENSEARCH_URL")
        try:
            with self._client() as client:
                index = self.opensearch_index or DEFAULT_LOG_INDEX
                url = f"{self.opensearch_url}/{index}/_search"

                filters: list[dict[str, Any]] = [
                    {"range": {"@timestamp": {"gte": f"now-{since_min}m"}}}
                ]
                if service:
                    filters.append({"term": {LOG_SERVICE_FIELD: service}})
                if level:
                    filters.append(
                        {"range": {"severity.number": {"gte": LOG_LEVEL_MIN[level]}}}
                    )
                body = {
                    "size": limit,
                    "query": {
                        "bool": {
                            "filter": filters,
                            "must_not": [
                                {
                                    "terms": {
                                        LOG_SERVICE_FIELD: sorted(EXCLUDED_SERVICES)
                                    }
                                }
                            ],
                        }
                    },
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
        key = fixture_key(op, kwargs)
        file_path = self.scenario_dir / f"{op}_{make_request_hash(op, key)}.json"
        payload = {"op": op, "kwargs": key, "data": fixture_data(op, data)}
        text = json.dumps(scrub_flags(payload), indent=1, sort_keys=True, default=str)
        file_path.write_text(FIXTURE_SCRUB.sub(FLAG_REDACTED, text), encoding="utf-8")

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
        req_hash = make_request_hash(op, fixture_key(op, kwargs))
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
        )[:limit]

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
        )[:limit]


def get_backend() -> TelemetryBackend:
    """Return the TelemetryBackend chosen by TELEMETRY_BACKEND (process env or oncall/.env)."""
    mode = load_settings().TELEMETRY_BACKEND.lower()
    scenario = os.environ.get("OFFLINE_SCENARIO", "baseline")

    if mode == "offline":
        return OfflineBackend(scenario=scenario)
    elif mode in ("record", "recording"):
        return RecordingBackend(scenario=scenario)
    return LiveBackend()
