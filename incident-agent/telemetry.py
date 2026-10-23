"""
Read-only telemetry tools for the Incident Zero agent.
Owner: Neha (Member 2).

What this module does
- Queries Prometheus (metrics), Jaeger v3 (traces) and OpenSearch PPL (logs).
- Only fixed query templates. Service names are validated against the observed
  inventory, time windows are bounded, every request has a timeout.
- Every call returns a ToolResult with status ok / empty / unavailable / error,
  so "no data" is never confused with "healthy".
- Every result is saved immediately as an evidence file (evidence/<id>.json),
  so each diagnosis citation can be traced back to a real capture.
- Feature-flag data is filtered out (flagd services, feature_flag span
  events/attributes, flag-related log lines). Diagnosis must come from telemetry.

What this module never does
- No writes, no shell commands, no Docker socket, no arbitrary URLs or
  model-written queries.

Quick check (Windows PowerShell, inside incident-agent/):
    python telemetry.py check
    python telemetry.py overview
    python telemetry.py traces payment
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

try:  # optional: load incident-agent/.env when present
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

# --------------------------------------------------------------------------
# Configuration (fixed by the operator, never chosen by the model)
# --------------------------------------------------------------------------
PROM_URL = os.getenv("PROM_URL", "http://localhost:9090").rstrip("/")
JAEGER_URL = os.getenv("JAEGER_URL", "http://localhost:8080").rstrip("/")
# OpenSearch host port is assigned dynamically by Docker: `docker port opensearch 9200`
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "").rstrip("/")
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", "evidence"))
REQUEST_TIMEOUT_S = float(os.getenv("TELEMETRY_TIMEOUT_S", "10"))

MIN_WINDOW_MIN, MAX_WINDOW_MIN = 1, 60
MAX_ITEMS = 20            # max traces / log lines returned to the model
EXCERPT_CHARS = 300       # max chars per log body / error message
MAX_LLM_CHARS = 3500      # max chars of one result shown to the model
INVENTORY_TTL_S = 60

EXCLUDED_SERVICES = {"flagd", "flagd-ui"}   # flag state is out of bounds
_FLAG_PATTERN = re.compile(r"feature[_.]?flag|flagd|openfeature", re.IGNORECASE)
_SERVICE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")

_client = httpx.Client(timeout=REQUEST_TIMEOUT_S, follow_redirects=False)


# --------------------------------------------------------------------------
# Shared record (keep in sync with Harsha's models.py when it lands)
# --------------------------------------------------------------------------
class ToolStatus(str, Enum):
    OK = "ok"                    # data found
    EMPTY = "empty"              # backend answered, but no data in the window
    UNAVAILABLE = "unavailable"  # backend not reachable / not configured
    ERROR = "error"              # backend answered with an error


class ToolResult(BaseModel):
    status: ToolStatus
    evidence_id: str
    tool: str
    source: Literal["prometheus", "jaeger", "opensearch", "derived"]
    service: str | None = None
    query: str
    window_start: datetime
    window_end: datetime
    collected_at: datetime
    value: Any = None
    excerpt: str | None = None
    trace_ids: list[str] = Field(default_factory=list)
    log_ids: list[str] = Field(default_factory=list)
    capture_ref: str | None = None
    message: str | None = None

    def for_llm(self) -> str:
        """Compact JSON for the diagnosis model (bounded size)."""
        data = {
            "evidence_id": self.evidence_id,
            "tool": self.tool,
            "status": self.status.value,
            "service": self.service,
            "window": f"{self.window_start:%H:%M:%S}-{self.window_end:%H:%M:%S}Z",
            "message": self.message,
            "value": self.value,
        }
        text = json.dumps(data, default=str)
        return text if len(text) <= MAX_LLM_CHARS else text[:MAX_LLM_CHARS] + '..."(truncated)"'


class TelemetryInputError(ValueError):
    """Raised for invalid tool arguments (unknown service, bad window, unknown tool)."""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window(minutes: int, minimum: int = MIN_WINDOW_MIN) -> tuple[datetime, datetime]:
    if not isinstance(minutes, int) or not (minimum <= minutes <= MAX_WINDOW_MIN):
        raise TelemetryInputError(f"window_minutes must be an integer {minimum}-{MAX_WINDOW_MIN}")
    end = _now()
    return end - timedelta(minutes=minutes), end


def _rfc3339(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    """One request with a single retry for transient failures. Raises httpx errors."""
    for attempt in (1, 2):
        try:
            resp = _client.request(method, url, **kwargs)
            if resp.status_code >= 500 and attempt == 1:
                time.sleep(0.5)
                continue
            return resp
        except (httpx.ConnectError, httpx.TimeoutException):
            if attempt == 2:
                raise
            time.sleep(0.5)
    raise RuntimeError("unreachable")  # pragma: no cover


def _capture(result: ToolResult, raw: Any) -> ToolResult:
    """Save the result (+ bounded raw response) as an evidence file."""
    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        path = EVIDENCE_DIR / f"{result.evidence_id}.json"
        raw_text = json.dumps(raw, default=str)
        if len(raw_text) > 50_000:
            raw_text = raw_text[:50_000] + "...(truncated)"
        result.capture_ref = str(path)
        path.write_text(
            json.dumps({"result": result.model_dump(mode="json"), "raw": raw_text}, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:  # capture failure must never hide the result
        result.capture_ref = None  # never point local_capture_reference at a file that wasn't written
        result.message = f"{result.message or ''} [capture failed: {exc}]".strip()
    return result


def _result(tool: str, source: str, service: str | None, query: str,
            start: datetime, end: datetime, status: ToolStatus, *, raw: Any = None,
            **fields) -> ToolResult:
    res = ToolResult(
        status=status,
        evidence_id=f"ev-{tool}-{uuid.uuid4().hex[:8]}",
        tool=tool, source=source, service=service, query=query,
        window_start=start, window_end=end, collected_at=_now(), **fields,
    )
    return _capture(res, raw)


def _failure(exc: Exception, tool: str, source: str, service: str | None, query: str,
             start: datetime, end: datetime) -> ToolResult:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        status, msg = ToolStatus.UNAVAILABLE, f"{source} not reachable: {type(exc).__name__}"
    else:
        status, msg = ToolStatus.ERROR, f"{source} error: {type(exc).__name__}: {str(exc)[:200]}"
    return _result(tool, source, service, query, start, end, status, message=msg)


def _short(text: Any) -> str:
    s = str(text) if text is not None else ""
    return s if len(s) <= EXCERPT_CHARS else s[:EXCERPT_CHARS] + "..."


# --------------------------------------------------------------------------
# Service inventory and validation
# --------------------------------------------------------------------------
_inventory: tuple[float, list[str]] = (0.0, [])


def service_inventory(refresh: bool = False) -> list[str]:
    """Services observed in Prometheus and Jaeger (flag services excluded)."""
    global _inventory
    if not refresh and _inventory[1] and time.time() - _inventory[0] < INVENTORY_TTL_S:
        return _inventory[1]
    names: set[str] = set()
    try:
        r = _request("GET", f"{PROM_URL}/api/v1/label/service_name/values")
        if r.status_code == 200:
            names.update(r.json().get("data") or [])
    except httpx.HTTPError:
        pass
    try:
        r = _request("GET", f"{JAEGER_URL}/jaeger/ui/api/v3/services")
        if r.status_code == 200:
            names.update(r.json().get("services") or [])
    except httpx.HTTPError:
        pass
    found = sorted(n for n in names if n and n not in EXCLUDED_SERVICES)
    if found:
        _inventory = (time.time(), found)
    return found


def validate_service(service: str) -> str:
    if not isinstance(service, str):
        raise TelemetryInputError("service must be a string")
    name = service.strip()
    if name in EXCLUDED_SERVICES:
        raise TelemetryInputError(f"'{name}' is out of bounds (feature-flag service)")
    if not _SERVICE_PATTERN.match(name):
        raise TelemetryInputError(f"invalid service name: {service!r}")
    inventory = service_inventory()
    if inventory and name not in inventory:
        raise TelemetryInputError(f"unknown service '{name}'. Known: {', '.join(inventory)}")
    return name


# --------------------------------------------------------------------------
# METRICS (Prometheus) - fixed templates only
# --------------------------------------------------------------------------
_CALLS = "traces_span_metrics_calls_total"
_DUR = "traces_span_metrics_duration_milliseconds_bucket"

METRIC_TEMPLATES: dict[str, tuple[str, str, str]] = {
    # name: (PromQL template, unit, label to keep in output)
    "request_rate": (f'sum(rate({_CALLS}{{service_name="{{s}}"}}[{{w}}m]))', "requests/s", ""),
    # "or vector(0)": traffic with zero errors is 0, not "no data"; no traffic stays empty.
    "error_rate": (
        f'(sum(rate({_CALLS}{{service_name="{{s}}",status_code="STATUS_CODE_ERROR"}}[{{w}}m])) or vector(0))'
        f' / sum(rate({_CALLS}{{service_name="{{s}}"}}[{{w}}m]))', "ratio 0-1", ""),
    "errors_by_operation": (
        f'topk(10, sum by (span_name) (rate({_CALLS}{{service_name="{{s}}",status_code="STATUS_CODE_ERROR"}}[{{w}}m])))',
        "errors/s", "span_name"),
    "p95_latency_ms": (
        f'histogram_quantile(0.95, sum by (le) (rate({_DUR}{{service_name="{{s}}"}}[{{w}}m])))', "ms", ""),
    "p95_latency_by_operation": (
        f'topk(10, histogram_quantile(0.95, sum by (le, span_name) (rate({_DUR}{{service_name="{{s}}"}}[{{w}}m]))))',
        "ms", "span_name"),
    # Container resource telemetry from the collector's docker_stats receiver.
    # Exact metric names are matched by pattern; confirm with `python telemetry.py names container`.
    "container_cpu": ('{__name__=~"container_cpu_utilization.*",container_name="{s}"}', "ratio/percent", "__name__"),
    "container_memory": ('{__name__=~"container_memory_(usage_total|percent|rss).*",container_name="{s}"}',
                         "bytes/percent", "__name__"),
    "container_memory_trend": ('deriv({__name__=~"container_memory_usage_total.*",container_name="{s}"}[{w}m])',
                               "bytes/s (positive = growing)", ""),
    "container_uptime": ('{__name__=~"container_uptime.*",container_name="{s}"}', "s", ""),
}
MetricName = Literal[
    "request_rate", "error_rate", "errors_by_operation", "p95_latency_ms", "p95_latency_by_operation",
    "container_cpu", "container_memory", "container_memory_trend", "container_uptime",
]


def _prom(promql: str) -> tuple[list[dict], Any]:
    r = _request("GET", f"{PROM_URL}/api/v1/query", params={"query": promql})
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise RuntimeError(body.get("error", "prometheus query failed"))
    rows = []
    for item in body["data"]["result"]:
        try:
            val = float(item["value"][1])
        except (KeyError, ValueError, TypeError):
            continue
        if val != val or val in (float("inf"), float("-inf")):  # NaN / inf -> no data
            continue
        rows.append({"labels": item.get("metric", {}), "value": round(val, 6)})
    return rows, body


def query_metrics(service: str, metric: str = "error_rate", window_minutes: int = 5) -> ToolResult:
    """Run one fixed metric template for one service over a bounded window."""
    service = validate_service(service)
    if metric not in METRIC_TEMPLATES:
        raise TelemetryInputError(f"unknown metric '{metric}'. Allowed: {', '.join(METRIC_TEMPLATES)}")
    start, end = _window(window_minutes, minimum=2)  # rate() needs >= 2 samples
    template, unit, keep = METRIC_TEMPLATES[metric]
    promql = template.replace("{s}", service).replace("{w}", str(window_minutes))
    try:
        rows, raw = _prom(promql)
    except Exception as exc:
        return _failure(exc, "query_metrics", "prometheus", service, promql, start, end)
    if not rows:
        msg = ("no data in window (no traffic, no errors recorded, or metric not exported)"
               if metric != "error_rate" else "no requests in window - cannot judge error rate")
        return _result("query_metrics", "prometheus", service, promql, start, end,
                       ToolStatus.EMPTY, raw=raw, value={"metric": metric, "unit": unit}, message=msg)
    if keep:
        series = [{keep: r["labels"].get(keep, ""), "value": r["value"]} for r in rows][:MAX_ITEMS]
        value = {"metric": metric, "unit": unit, "series": series}
    else:
        value = {"metric": metric, "unit": unit, "value": rows[0]["value"]}
    return _result("query_metrics", "prometheus", service, promql, start, end,
                   ToolStatus.OK, raw=raw, value=value)


def overview(window_minutes: int = 5) -> ToolResult:
    """All services at once: request rate, error rate and p95 latency (fixed templates).
    Good first step: shows where things changed without dumping raw data."""
    start, end = _window(window_minutes, minimum=2)
    w = window_minutes
    queries = {
        "request_rate": f"sum by (service_name) (rate({_CALLS}[{w}m]))",
        "error_rate": (f'(sum by (service_name) (rate({_CALLS}{{status_code="STATUS_CODE_ERROR"}}[{w}m]))'
                       f" or sum by (service_name) (rate({_CALLS}[{w}m])) * 0)"
                       f" / sum by (service_name) (rate({_CALLS}[{w}m]))"),
        "p95_ms": f"histogram_quantile(0.95, sum by (le, service_name) (rate({_DUR}[{w}m])))",
    }
    table: dict[str, dict[str, float]] = {}
    raws = {}
    try:
        for key, q in queries.items():
            rows, raws[key] = _prom(q)
            for r in rows:
                svc = r["labels"].get("service_name")
                if svc and svc not in EXCLUDED_SERVICES:
                    table.setdefault(svc, {})[key] = r["value"]
    except Exception as exc:
        return _failure(exc, "overview", "prometheus", None, json.dumps(queries), start, end)
    if not table:
        return _result("overview", "prometheus", None, json.dumps(queries), start, end,
                       ToolStatus.EMPTY, raw=raws, message="no span metrics in window (is load running?)")
    rows = [{"service": s, **v} for s, v in table.items()]
    rows.sort(key=lambda r: (-(r.get("error_rate") or 0), -(r.get("p95_ms") or 0)))
    return _result("overview", "prometheus", None, json.dumps(queries), start, end,
                   ToolStatus.OK, raw=raws, value={"services": rows[:30], "units":
                   {"request_rate": "req/s", "error_rate": "ratio 0-1", "p95_ms": "ms"}})


# --------------------------------------------------------------------------
# TRACES (Jaeger v3 API, through the frontend proxy)
# --------------------------------------------------------------------------
_SAFE_ATTR = re.compile(r"^(http\.|rpc\.|db\.|server\.|peer\.|error\.|net\.|network\.|url\.|exception\.)")


def _attr_value(v: dict) -> Any:
    for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if k in v:
            return v[k]
    return None


def _attrs(items: list[dict] | None) -> dict[str, Any]:
    return {a.get("key"): _attr_value(a.get("value", {})) for a in (items or []) if a.get("key")}


def _hex_id(value: str) -> str:
    """Jaeger may return ids as hex or base64; normalise to lowercase hex."""
    if not value:
        return ""
    if re.fullmatch(r"[0-9a-fA-F]{16}|[0-9a-fA-F]{32}", value):
        return value.lower()
    try:
        return base64.b64decode(value, validate=True).hex()
    except (binascii.Error, ValueError):
        return value


def _is_error(status: dict) -> bool:
    code = status.get("code")
    return code in (2, "2", "STATUS_CODE_ERROR", "Error", "ERROR")


def _parse_span(sp: dict, service: str) -> dict:
    attrs = _attrs(sp.get("attributes"))
    status = sp.get("status") or {}
    exception = None
    for ev in sp.get("events") or []:
        name = ev.get("name", "")
        if _FLAG_PATTERN.search(name):
            continue  # never pass feature-flag evaluations to the model
        if name == "exception":
            ea = _attrs(ev.get("attributes"))
            exception = _short(f"{ea.get('exception.type', '')}: {ea.get('exception.message', '')}")
    try:
        dur_ms = (int(sp.get("endTimeUnixNano", 0)) - int(sp.get("startTimeUnixNano", 0))) / 1e6
    except (TypeError, ValueError):
        dur_ms = None
    return {
        "span_id": _hex_id(sp.get("spanId", "")),
        "parent_id": _hex_id(sp.get("parentSpanId", "")),
        "service": service,
        "name": sp.get("name"),
        "duration_ms": round(dur_ms, 1) if dur_ms is not None else None,
        "error": _is_error(status),
        "error_message": _short(status.get("message")) or exception,
        "start_ns": int(sp.get("startTimeUnixNano", 0) or 0),
        "attributes": {k: _short(v) for k, v in attrs.items()
                       if _SAFE_ATTR.match(k) and not _FLAG_PATTERN.search(k)},
    }


def _error_origin(spans: list[dict]) -> dict | None:
    """Deepest error span whose children have no errors = where the failure starts."""
    by_parent: dict[str, list[dict]] = {}
    for s in spans:
        by_parent.setdefault(s["parent_id"], []).append(s)
    candidates = [s for s in spans if s["error"] and
                  not any(c["error"] for c in by_parent.get(s["span_id"], []))]
    if not candidates:
        return None
    ids = {s["span_id"]: s for s in spans}

    def depth(s: dict) -> int:
        d, seen = 0, set()
        while s["parent_id"] in ids and s["parent_id"] not in seen:
            seen.add(s["parent_id"])
            s, d = ids[s["parent_id"]], d + 1
        return d

    o = max(candidates, key=depth)
    return {"service": o["service"], "operation": o["name"], "error_message": o["error_message"],
            "span_id": o["span_id"]}


def search_traces(service: str, window_minutes: int = 15, errors_only: bool = True,
                  limit: int = 10) -> ToolResult:
    """Recent traces for a service: error spans, suspected error origin per trace,
    and observed caller->callee edges (dependency map)."""
    service = validate_service(service)
    start, end = _window(window_minutes)
    limit = max(1, min(int(limit), MAX_ITEMS))
    params = {
        "query.service_name": service,
        "query.num_traces": min(limit * 4 if errors_only else limit, 100),
        "query.start_time_min": _rfc3339(start),
        "query.start_time_max": _rfc3339(end),
    }
    url = f"{JAEGER_URL}/jaeger/ui/api/v3/traces"
    query = f"GET /jaeger/ui/api/v3/traces {json.dumps(params)}"
    try:
        r = _request("GET", url, params=params)
        if r.status_code == 404:  # Jaeger v3 answers 404 when no traces match
            return _result("search_traces", "jaeger", service, query, start, end,
                           ToolStatus.EMPTY, raw=r.text[:2000], message="no traces in window")
        r.raise_for_status()
        raw = r.json()
    except Exception as exc:
        return _failure(exc, "search_traces", "jaeger", service, query, start, end)

    traces: dict[str, list[dict]] = {}
    for rs in (raw.get("result") or {}).get("resourceSpans") or []:
        svc = _attrs((rs.get("resource") or {}).get("attributes")).get("service.name", "unknown")
        if svc in EXCLUDED_SERVICES:
            continue  # flag-service spans (and their edges) are out of bounds
        for ss in rs.get("scopeSpans") or []:
            for sp in ss.get("spans") or []:
                traces.setdefault(_hex_id(sp.get("traceId", "")), []).append(_parse_span(sp, svc))

    summaries, origin_counts, edges = [], {}, {}
    for tid, spans in traces.items():
        ids = {s["span_id"]: s for s in spans}
        for s in spans:  # dependency edges from parent/child spans
            parent = ids.get(s["parent_id"])
            if parent and parent["service"] != s["service"]:
                key = f'{parent["service"]} -> {s["service"]}'
                edges[key] = edges.get(key, 0) + 1
        errs = [s for s in spans if s["error"]]
        if errors_only and not errs:
            continue
        origin = _error_origin(spans)
        if origin:
            origin_counts[origin["service"]] = origin_counts.get(origin["service"], 0) + 1
        root = min(spans, key=lambda s: s["start_ns"])
        summaries.append({
            "trace_id": tid,
            "root": f'{root["service"]}: {root["name"]}',
            "duration_ms": root["duration_ms"],
            "services": sorted({s["service"] for s in spans}),
            "error_spans": [{k: s[k] for k in ("service", "name", "error_message", "duration_ms", "attributes")}
                            for s in errs[:4]],
            "suspected_origin": origin,
            "_start": root["start_ns"],
        })
    summaries.sort(key=lambda t: t["_start"], reverse=True)
    for t in summaries:
        t.pop("_start")
    summaries = summaries[:limit]

    if not summaries:
        msg = ("traces found but none with errors in window" if errors_only and traces
               else "no traces in window")
        return _result("search_traces", "jaeger", service, query, start, end, ToolStatus.EMPTY,
                       raw=raw, value={"traces_scanned": len(traces), "edges": edges}, message=msg)
    value = {
        "traces_scanned": len(traces),
        "error_origin_counts": dict(sorted(origin_counts.items(), key=lambda kv: -kv[1])),
        "edges": dict(sorted(edges.items(), key=lambda kv: -kv[1])[:20]),
        "traces": summaries,
    }
    return _result("search_traces", "jaeger", service, query, start, end, ToolStatus.OK,
                   raw=raw, value=value, trace_ids=[t["trace_id"] for t in summaries])


# --------------------------------------------------------------------------
# LOGS (OpenSearch PPL, read-only)
# --------------------------------------------------------------------------
_SEVERITY = {"DEBUG": 5, "INFO": 9, "WARN": 13, "ERROR": 17, "FATAL": 21}


def _ppl(query: str) -> dict:
    r = _request("POST", f"{OPENSEARCH_URL}/_plugins/_ppl", json={"query": query},
                 headers={"Content-Type": "application/json"})
    r.raise_for_status()
    return r.json()


def _rows(body: dict) -> list[dict]:
    cols = [c.get("name") for c in body.get("schema", [])]
    return [dict(zip(cols, row)) for row in body.get("datarows", [])]


def _pick(row: dict, *keys: str) -> Any:
    for k in keys:
        if row.get(k) not in (None, ""):
            return row[k]
    return None


def query_logs(service: str, window_minutes: int = 10, min_severity: str = "WARN",
               limit: int = 20) -> ToolResult:
    """Recent log lines for a service at or above a severity (WARN by default)."""
    service = validate_service(service)
    start, end = _window(window_minutes)
    min_severity = str(min_severity).upper()
    if min_severity not in _SEVERITY:
        raise TelemetryInputError(f"min_severity must be one of {', '.join(_SEVERITY)}")
    limit = max(1, min(int(limit), MAX_ITEMS))
    if not OPENSEARCH_URL:
        return _result("query_logs", "opensearch", service, "-", start, end, ToolStatus.UNAVAILABLE,
                       message="OPENSEARCH_URL not set. Find the port with: docker port opensearch 9200")
    since = start.strftime("%Y-%m-%d %H:%M:%S")
    sev = _SEVERITY[min_severity]
    primary = (f"source=otel-logs-* | where resource.service.name = '{service}'"
               f" and `@timestamp` >= '{since}' and `severity.number` >= {sev}"
               f" | sort - `@timestamp` | head {limit * 2}"
               f" | fields `@timestamp`, severity, body, traceId, _id")  # _id -> log_ids
    fallback = (f"source=otel-logs-* | where resource.service.name = '{service}'"
                f" and `@timestamp` >= '{since}' | sort - `@timestamp` | head {limit * 5}")
    used = primary
    try:
        try:
            body = _ppl(primary)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 400:
                raise
            used = fallback  # field names differ in this index: filter severity client-side
            body = _ppl(fallback)
    except Exception as exc:
        return _failure(exc, "query_logs", "opensearch", service, used, start, end)

    lines, dropped = [], 0
    for row in _rows(body):
        text = _pick(row, "body", "body.text", "message")
        sev_obj = row.get("severity") if isinstance(row.get("severity"), dict) else {}  # otel-logs-*: {"number", "text"}
        sev_text = str(_pick(sev_obj, "text") or _pick(row, "severity.text", "severityText", "severity_text") or "")
        sev_num = _pick(sev_obj, "number") or _pick(row, "severity.number", "severityNumber")
        if used == fallback:
            try:
                ok = int(sev_num) >= sev if sev_num is not None else _SEVERITY.get(sev_text.upper()[:5], 0) >= sev
            except (TypeError, ValueError):
                ok = True
            if not ok:
                continue
        if text and _FLAG_PATTERN.search(str(text)):
            dropped += 1  # flag-related log lines are out of bounds for diagnosis
            continue
        lines.append({
            "time": _pick(row, "@timestamp", "observedTimestamp", "time"),
            "severity": sev_text or sev_num,
            "body": _short(text if not isinstance(text, (dict, list)) else json.dumps(text)),
            "trace_id": _hex_id(str(_pick(row, "traceId", "trace_id") or "")),
            "log_id": str(row.get("_id") or ""),
        })
        if len(lines) >= limit:
            break

    msg = f"{dropped} flag-related line(s) withheld" if dropped else None
    if not lines:
        return _result("query_logs", "opensearch", service, used, start, end, ToolStatus.EMPTY,
                       raw=body, message=f"no {min_severity}+ logs in window" + (f"; {msg}" if msg else ""))
    return _result("query_logs", "opensearch", service, used, start, end, ToolStatus.OK, raw=body,
                   value={"min_severity": min_severity, "count": len(lines), "lines": lines},
                   excerpt=lines[0]["body"], message=msg,
                   trace_ids=sorted({l["trace_id"] for l in lines if l["trace_id"]}),
                   log_ids=[l["log_id"] for l in lines if l["log_id"]])


# --------------------------------------------------------------------------
# HEALTH (derived from telemetry only)
# --------------------------------------------------------------------------
def service_health(service: str, window_minutes: int = 5) -> ToolResult:
    """One-call health summary for a service, derived from metrics only:
    traffic, errors, latency, container CPU/memory/uptime (restart detection)."""
    service = validate_service(service)
    start, end = _window(window_minutes, minimum=2)
    parts = ["request_rate", "error_rate", "p95_latency_ms", "container_cpu",
             "container_memory", "container_memory_trend", "container_uptime"]
    summary, refs, statuses = {}, [], set()
    for m in parts:
        r = query_metrics(service, m, window_minutes)
        refs.append(r.evidence_id)
        statuses.add(r.status)
        summary[m] = r.value.get("value", r.value.get("series")) if r.status == ToolStatus.OK and r.value else r.status.value
    uptime = summary.get("container_uptime")
    if isinstance(uptime, (int, float)):
        summary["recently_restarted"] = uptime < window_minutes * 60
    if statuses == {ToolStatus.UNAVAILABLE}:
        status = ToolStatus.UNAVAILABLE
    elif ToolStatus.OK in statuses:
        status = ToolStatus.OK
    elif ToolStatus.ERROR in statuses:
        status = ToolStatus.ERROR
    else:
        status = ToolStatus.EMPTY
    # Sub-query IDs stay in the capture file only: they are not registered as Evidence,
    # so showing them to the model would invite citations the report gate rejects.
    return _result("service_health", "derived", service, ", ".join(parts), start, end, status,
                   raw={"sub_evidence": refs}, value={"summary": summary})


# --------------------------------------------------------------------------
# Registry for the diagnosis module (Member 3): validated, read-only tools only
# --------------------------------------------------------------------------
class _OverviewArgs(BaseModel):
    window_minutes: int = Field(5, ge=2, le=MAX_WINDOW_MIN)


class _MetricsArgs(BaseModel):
    service: str
    metric: MetricName = "error_rate"
    window_minutes: int = Field(5, ge=2, le=MAX_WINDOW_MIN)


class _TracesArgs(BaseModel):
    service: str
    window_minutes: int = Field(15, ge=1, le=MAX_WINDOW_MIN)
    errors_only: bool = True
    limit: int = Field(10, ge=1, le=MAX_ITEMS)


class _LogsArgs(BaseModel):
    service: str
    window_minutes: int = Field(10, ge=1, le=MAX_WINDOW_MIN)
    min_severity: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"] = "WARN"
    limit: int = Field(20, ge=1, le=MAX_ITEMS)


class _HealthArgs(BaseModel):
    service: str
    window_minutes: int = Field(5, ge=2, le=MAX_WINDOW_MIN)


TOOLS = {
    "overview": (overview, _OverviewArgs,
                 "All services: request rate, error rate, p95 latency. Start here."),
    "query_metrics": (query_metrics, _MetricsArgs,
                      "One fixed metric for one service (errors, latency, per-operation, container CPU/memory/uptime)."),
    "search_traces": (search_traces, _TracesArgs,
                      "Recent (error) traces for a service with trace IDs, error messages, suspected error origin and call edges."),
    "query_logs": (query_logs, _LogsArgs, "Recent log lines for a service at or above a severity."),
    "service_health": (service_health, _HealthArgs,
                       "Health summary for one service from metrics: traffic, errors, latency, CPU, memory, restarts."),
}


def tool_specs() -> list[dict]:
    """OpenAI-style function specs for the LLM."""
    return [{"type": "function", "function": {
        "name": name, "description": desc, "parameters": args.model_json_schema()}}
        for name, (_, args, desc) in TOOLS.items()]


def run_tool(name: str, arguments: dict | None) -> ToolResult:
    """Validate and run one tool. Raises TelemetryInputError for unknown tools/bad args."""
    if name not in TOOLS:
        raise TelemetryInputError(f"unknown tool '{name}'")
    fn, args_model, _ = TOOLS[name]
    try:
        args = args_model.model_validate(arguments or {})
    except ValidationError as exc:
        raise TelemetryInputError(f"bad arguments for {name}: {exc.errors()[:3]}") from exc
    return fn(**args.model_dump())


# --------------------------------------------------------------------------
# CLI for CP0/CP1 checks
# --------------------------------------------------------------------------
def check_backends() -> dict[str, str]:
    """Connectivity check for CP0: is each telemetry backend reachable and returning data?"""
    report = {}
    for name, method, url in [
        ("prometheus", "GET", f"{PROM_URL}/-/ready"),
        ("jaeger", "GET", f"{JAEGER_URL}/jaeger/ui/api/v3/services"),
        ("opensearch", "GET", f"{OPENSEARCH_URL}/_cluster/health" if OPENSEARCH_URL else ""),
    ]:
        if not url:
            report[name] = "NOT CONFIGURED (set OPENSEARCH_URL; port: docker port opensearch 9200)"
            continue
        try:
            r = _request(method, url)
            report[name] = f"HTTP {r.status_code}" + (" OK" if r.status_code == 200 else "")
        except httpx.HTTPError as exc:
            report[name] = f"UNREACHABLE ({type(exc).__name__}) at {url}"
    inv = service_inventory(refresh=True)
    report["services_seen"] = f"{len(inv)}: {', '.join(inv)}" if inv else "none yet (wait for load)"
    return report


def _print(result: ToolResult) -> None:
    print(json.dumps(result.model_dump(mode="json", exclude={"window_start", "window_end"}),
                     indent=2, default=str)[:6000])


def main() -> None:
    p = argparse.ArgumentParser(description="Read-only telemetry tools")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("inventory")
    o = sub.add_parser("overview"); o.add_argument("--window", type=int, default=5)
    m = sub.add_parser("metrics"); m.add_argument("service"); m.add_argument("metric", nargs="?", default="error_rate")
    m.add_argument("--window", type=int, default=5)
    t = sub.add_parser("traces"); t.add_argument("service"); t.add_argument("--window", type=int, default=15)
    t.add_argument("--all", action="store_true", help="include traces without errors")
    lg = sub.add_parser("logs"); lg.add_argument("service"); lg.add_argument("--window", type=int, default=10)
    lg.add_argument("--severity", default="WARN")
    h = sub.add_parser("health"); h.add_argument("service"); h.add_argument("--window", type=int, default=5)
    n = sub.add_parser("names", help="list Prometheus metric names containing text")
    n.add_argument("contains")
    a = p.parse_args()
    try:
        if a.cmd == "check":
            for k, v in check_backends().items():
                print(f"{k:14} {v}")
        elif a.cmd == "inventory":
            print("\n".join(service_inventory(refresh=True)) or "(none)")
        elif a.cmd == "overview":
            _print(overview(a.window))
        elif a.cmd == "metrics":
            _print(query_metrics(a.service, a.metric, a.window))
        elif a.cmd == "traces":
            _print(search_traces(a.service, a.window, errors_only=not a.all))
        elif a.cmd == "logs":
            _print(query_logs(a.service, a.window, a.severity))
        elif a.cmd == "health":
            _print(service_health(a.service, a.window))
        elif a.cmd == "names":
            r = _request("GET", f"{PROM_URL}/api/v1/label/__name__/values")
            print("\n".join(x for x in r.json().get("data", []) if a.contains in x))
    except TelemetryInputError as exc:
        print(f"Input rejected: {exc}")


if __name__ == "__main__":
    main()
