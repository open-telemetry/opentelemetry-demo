"""Observability tools the incident agent can call.

Every tool returns a dict with a ``status`` of ``ok``, ``no_data``, ``source_unavailable``
or ``error``. Missing or unreachable telemetry is never reported as healthy.

Every citable fact carries an evidence entry ``{"ref", "kind", ...}``. The evidence
validator only accepts citations whose ``ref`` (and value, for metrics) appears here.

Query contracts, checked against the running demo on 2026-10-23:
  verified-live: span metrics ``traces_span_metrics_calls_total`` and
    ``traces_span_metrics_duration_milliseconds_bucket`` labelled by service_name,
    span_kind, span_name, status_code; ``container_cpu_utilization_ratio`` and
    ``container_memory_usage_total_bytes`` labelled by container_name; Jaeger v3 API
    under ``/jaeger/ui/api/v3`` (``query.duration_min`` takes values like ``100ms``);
    OpenSearch ``otel-logs-*`` with ``severity.text`` (mixed case), ``severity.number``,
    ``resource.service.name`` (.keyword), ``body``, ``traceId``, ``observedTimestamp``.
  pending: error-path shapes (status.code 2 spans, error logs, restarting containers)
    have not yet been seen live because no practice incident has been injected.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import jsonschema

from ..config import Settings
from ..telemetry.exceptions import TelemetryError
from ..telemetry.jaeger_client import JaegerClient
from ..telemetry.opensearch_client import OpenSearchClient
from ..telemetry.prometheus_client import PrometheusClient

OK = "ok"
NO_DATA = "no_data"
SOURCE_UNAVAILABLE = "source_unavailable"
ERROR = "error"

# Organiser rule: reading feature-flag settings to diagnose means disqualification.
# The flag services are excluded and flag-related span data is stripped from all output.
EXCLUDED_SERVICES = frozenset({"flagd", "flagd-ui"})
# Observability tooling containers that are not part of the shop; left out of the overview.
TOOLING_CONTAINERS = frozenset({"grafana", "telemetry-docs", "opamp-server", "jaeger", "prometheus",
                                "opensearch", "load-generator", "agent", "mcp", "chatbot"})
# Matches attribute/event/metric names that could reveal feature-flag state.
_FLAG_NAME = re.compile(r"feature_flag|featureflag|flagd|openfeature", re.IGNORECASE)

MAX_RESULT_CHARS = 9000
SERVER_KINDS = 'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"'

# Static topology of the OpenTelemetry Demo (callee lists), from the demo's architecture
# docs and the evidence collector's DEFAULT_SERVICE_EDGES. Infra nodes use container names.
TOPOLOGY: Dict[str, List[str]] = {
    "load-generator": ["frontend-proxy"],
    "frontend-proxy": ["frontend", "image-provider"],
    "frontend": ["ad", "cart", "checkout", "currency", "product-catalog", "recommendation", "shipping"],
    "checkout": ["cart", "currency", "email", "payment", "product-catalog", "shipping", "kafka"],
    "cart": ["valkey-cart"],
    "recommendation": ["product-catalog"],
    "product-catalog": ["astronomy-db"],
    "shipping": ["quote"],
    "accounting": ["kafka", "astronomy-db"],
    "fraud-detection": ["kafka"],
    "ad": [],
    "currency": [],
    "email": [],
    "payment": [],
    "quote": [],
    "image-provider": [],
    "valkey-cart": [],
    "astronomy-db": [],
    "kafka": [],
}

# All known demo microservices and infrastructure containers in the Astronomy Shop ecosystem
DEMO_CONTAINERS: frozenset[str] = frozenset(
    set(TOPOLOGY.keys())
    | {callee for callees in TOPOLOGY.values() for callee in callees}
    | TOOLING_CONTAINERS
    | {"astronomy-db", "otel-collector", "valkey-cart", "valkey", "postgresql"}
) - EXCLUDED_SERVICES


def _extract_compose_project(labels: Any) -> Optional[str]:
    """Extract com.docker.compose.project from inspect dict or docker ps label string."""
    if isinstance(labels, dict):
        p = labels.get("com.docker.compose.project")
        return str(p).strip() if p else None
    if isinstance(labels, str):
        for part in labels.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                if k.strip() == "com.docker.compose.project":
                    return v.strip()
    return None


def _discover_compose_project(ctx: ToolContext) -> Optional[str]:
    """Discover the Docker Compose project name from env, settings, or anchor containers."""
    env_proj = os.environ.get("COMPOSE_PROJECT_NAME", "").strip()
    if env_proj:
        return env_proj
    settings_proj = getattr(ctx.settings, "compose_project_name", None)
    if settings_proj:
        return str(settings_proj).strip()
    for anchor in ("frontend", "frontend-proxy", "otel-collector", "jaeger", "prometheus"):
        try:
            raw = ctx.docker(["inspect", "--format", "{{json .Config.Labels}}", anchor])
            labels = json.loads(raw)
            p = _extract_compose_project(labels)
            if p:
                return p
        except Exception:
            continue
    return None


def _scoped_container_names(ctx: ToolContext) -> List[str]:
    """Return container names scoped to the demo Compose project, falling back to known demo identities."""
    proj = _discover_compose_project(ctx)
    last_err: Optional[Exception] = None
    if proj:
        try:
            raw = ctx.docker(["ps", "-a", "--filter", f"label=com.docker.compose.project={proj}", "--format", "{{.Names}}"])
            names = [n.strip() for n in raw.split() if n.strip() and n.strip() not in EXCLUDED_SERVICES]
            if names:
                return sorted(set(n for n in names if n in DEMO_CONTAINERS))
        except Exception as e:
            last_err = e
    # Explicit conservative fallback: inspect host containers and keep only verified demo identities
    try:
        raw = ctx.docker(["ps", "-a", "--format", "{{json .}}"])
    except Exception as e:
        raise last_err or e
    names = []
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        name = row.get("Names", "").strip()
        if not name or name in EXCLUDED_SERVICES or name not in DEMO_CONTAINERS:
            continue
        c_proj = _extract_compose_project(row.get("Labels"))
        # Reject if container explicitly belongs to a known unrelated compose project
        if c_proj and c_proj not in ("opentelemetry-demo", "opentelemetry_demo", "otel-demo"):
            continue
        names.append(name)
    return sorted(set(names))


def _result(tool: str, status: str, summary: str, data: Any = None,
            evidence: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {"tool": tool, "status": status, "summary": summary,
            "data": data if data is not None else {}, "evidence": evidence or []}


def _round(v: Optional[float], nd: int = 4) -> Optional[float]:
    return None if v is None else round(float(v), nd)


def _clamp_window(minutes: Any, default: int, lo: int = 1, hi: int = 60) -> int:
    try:
        return max(lo, min(hi, int(minutes)))
    except (TypeError, ValueError):
        return default


def strip_flag_data(obj: Any) -> Any:
    """Recursively drop any key or attribute entry whose name looks flag-related."""
    if isinstance(obj, dict):
        if "key" in obj and isinstance(obj["key"], str) and _FLAG_NAME.search(obj["key"]):
            return None
        if "name" in obj and isinstance(obj["name"], str) and _FLAG_NAME.search(obj["name"]):
            return None
        if "ref" in obj and isinstance(obj["ref"], str) and _FLAG_NAME.search(obj["ref"]):
            return None
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and _FLAG_NAME.search(k):
                continue
            cleaned = strip_flag_data(v)
            if cleaned is None and v is not None:
                continue
            out[k] = cleaned
        return out
    if isinstance(obj, list):
        return [c for c in (strip_flag_data(x) for x in obj) if c is not None]
    return obj


def _evidence_subject(ref: str) -> str:
    """The token that must still appear in the data for an evidence entry to stay meaningful."""
    parts = ref.split(":")
    if parts[0] in ("metric", "container") and len(parts) > 1:
        return parts[1]
    if parts[0] == "span" and len(parts) > 1:
        return parts[1]
    return ref


def _prune_evidence(result: Dict[str, Any]) -> None:
    shown = json.dumps(result.get("data"), default=str)
    result["evidence"] = [e for e in result.get("evidence", []) or []
                          if _evidence_subject(str(e.get("ref", ""))) in shown]


def cap_result(result: Dict[str, Any], max_chars: int = MAX_RESULT_CHARS) -> Dict[str, Any]:
    """Shrink list payloads until the serialized result fits the size budget.

    Data rows are halved first (rows are already sorted most-relevant first), and evidence for
    rows that were cut is dropped with them, so every remaining citation is visible in the data.
    """
    if len(json.dumps(result, default=str)) <= max_chars:
        return result
    data = result.get("data")
    for _ in range(12):
        lists = _largest_lists(data)
        if not lists:
            break
        holder, key, items = lists[0]
        keep = max(1, len(items) // 2)
        holder[key] = items[:keep]
        result["truncated"] = True
        _prune_evidence(result)
        if len(json.dumps(result, default=str)) <= max_chars:
            return result
    evidence = result.get("evidence", [])
    while len(json.dumps(result, default=str)) > max_chars and len(evidence) > 1:
        evidence = evidence[: len(evidence) // 2]
        result["evidence"] = evidence
        result["truncated"] = True
    return result


def _largest_lists(obj: Any) -> List[Tuple[Any, Any, list]]:
    found: List[Tuple[Any, Any, list]] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, list) and len(v) > 1:
                    found.append((o, k, v))
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(obj)
    found.sort(key=lambda t: len(json.dumps(t[2], default=str)), reverse=True)
    return found


class ToolContext:
    """Backend clients plus endpoint discovery, shared by all tools."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        jaeger: Optional[JaegerClient] = None,
        prometheus: Optional[PrometheusClient] = None,
        opensearch: Optional[OpenSearchClient] = None,
        docker_runner: Optional[Callable[[List[str]], str]] = None,
        now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.jaeger = jaeger or JaegerClient(base_url=self.settings.jaeger_url)
        self.prometheus = prometheus or PrometheusClient(base_url=self.settings.prometheus_url)
        self._opensearch = opensearch
        self._docker = docker_runner or _run_docker
        self.now = now or (lambda: datetime.now(timezone.utc))

    def docker(self, args: List[str]) -> str:
        return self._docker(args)

    @property
    def opensearch(self) -> OpenSearchClient:
        if self._opensearch is None:
            self._opensearch = OpenSearchClient(base_url=self._resolve_opensearch_url())
        return self._opensearch

    def _resolve_opensearch_url(self) -> str:
        configured = self.settings.opensearch_url
        if OpenSearchClient(base_url=configured, timeout_seconds=3).health_check():
            return configured
        # The demo publishes OpenSearch on a random host port; ask Docker for it.
        try:
            out = self.docker(["port", "opensearch", "9200"]).strip().splitlines()
            port = out[0].rsplit(":", 1)[1] if out else ""
            if port.isdigit():
                return f"http://localhost:{port}"
        except Exception:
            pass
        return configured

    def prom_vector(self, promql: str) -> List[Tuple[Dict[str, str], float]]:
        data = self.prometheus.query(promql)
        out: List[Tuple[Dict[str, str], float]] = []
        for item in data.get("data", {}).get("result", []):
            try:
                val = float(item["value"][1])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if val != val:  # NaN from histogram_quantile on empty buckets
                continue
            out.append((item.get("metric", {}), val))
        return out

    def prom_by(self, promql: str, label: str) -> Dict[str, float]:
        return {m.get(label, ""): v for m, v in self.prom_vector(promql) if m.get(label)}


def _run_docker(args: List[str]) -> str:
    exe = shutil.which("docker") or "/usr/local/bin/docker"
    proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"docker {' '.join(args)} failed")
    return proc.stdout


# --------------------------------------------------------------------------- metrics


def _service_rates(ctx: ToolContext, w: str, offset: str = "") -> Dict[str, Dict[str, float]]:
    off = f" offset {offset}" if offset else ""
    calls = f"traces_span_metrics_calls_total{{{SERVER_KINDS}}}"
    errs = f'traces_span_metrics_calls_total{{{SERVER_KINDS},status_code="STATUS_CODE_ERROR"}}'
    buckets = f"traces_span_metrics_duration_milliseconds_bucket{{{SERVER_KINDS}}}"
    req = ctx.prom_by(f"sum by (service_name)(rate({calls}[{w}]{off}))", "service_name")
    err = ctx.prom_by(f"sum by (service_name)(rate({errs}[{w}]{off}))", "service_name")
    p95 = ctx.prom_by(
        f"histogram_quantile(0.95, sum by (service_name, le)(rate({buckets}[{w}]{off})))", "service_name")
    out: Dict[str, Dict[str, float]] = {}
    for svc, r in req.items():
        e = err.get(svc, 0.0)
        out[svc] = {"rps": r, "error_rate": (e / r) if r > 0 else 0.0, "p95_ms": p95.get(svc)}
    return out


def _container_states(ctx: ToolContext) -> Tuple[Optional[Dict[str, Dict[str, Any]]], Optional[str]]:
    proj = _discover_compose_project(ctx)
    raw = None
    last_err = None
    if proj:
        try:
            raw = ctx.docker(["ps", "-a", "--filter", f"label=com.docker.compose.project={proj}", "--format", "{{json .}}"])
        except Exception as e:
            last_err = str(e)[:200]
    if raw is None or not raw.strip():
        try:
            raw = ctx.docker(["ps", "-a", "--format", "{{json .}}"])
        except Exception as e:
            return None, last_err or str(e)[:200]
    states: Dict[str, Dict[str, Any]] = {}
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        name = row.get("Names", "")
        if not name or name in EXCLUDED_SERVICES or name not in DEMO_CONTAINERS:
            continue
        c_proj = _extract_compose_project(row.get("Labels"))
        if proj and c_proj and c_proj != proj:
            continue
        if not proj and c_proj and c_proj not in ("opentelemetry-demo", "opentelemetry_demo", "otel-demo"):
            continue
        states[name] = {"state": row.get("State", ""), "status": row.get("Status", "")}
    return states, None


def system_overview(ctx: ToolContext, window_minutes: int = 5) -> Dict[str, Any]:
    tool = "system_overview"
    m = _clamp_window(window_minutes, 5)
    w = f"{m}m"
    try:
        now_rates = _service_rates(ctx, w)
        base_rates = _service_rates(ctx, w, offset="30m")
        cpu = ctx.prom_by(f"avg by (container_name)(avg_over_time(container_cpu_utilization_ratio[{w}]))",
                          "container_name")
        mem = ctx.prom_by("avg by (container_name)(container_memory_usage_total_bytes)", "container_name")
        mem_prev = ctx.prom_by(f"avg by (container_name)(container_memory_usage_total_bytes offset {w})",
                               "container_name")
    except TelemetryError as e:
        return _result(tool, SOURCE_UNAVAILABLE, f"Prometheus unreachable: {str(e)[:200]}")
    states, docker_err = _container_states(ctx)

    services = sorted((set(now_rates) | set(cpu) | set(states or {})) - EXCLUDED_SERVICES - TOOLING_CONTAINERS)
    if not services:
        return _result(tool, NO_DATA, "Prometheus returned no service metrics for the window.")

    rows, evidence = [], []
    for svc in services:
        cur, base = now_rates.get(svc, {}), base_rates.get(svc, {})
        row: Dict[str, Any] = {"service": svc}
        flags: List[str] = []
        if cur:
            row.update(rps=_round(cur["rps"], 3), error_rate=_round(cur["error_rate"]),
                       p95_ms=_round(cur.get("p95_ms"), 1))
            row["baseline_error_rate"] = _round(base.get("error_rate")) if base else None
            row["baseline_p95_ms"] = _round(base.get("p95_ms"), 1) if base else None
            if cur["error_rate"] >= 0.05 and cur["error_rate"] > 2 * (base.get("error_rate") or 0) + 0.01:
                flags.append("error_rate_up")
            bp, cp = base.get("p95_ms"), cur.get("p95_ms")
            if cp and bp and cp > 2 * bp and cp > 200:
                flags.append("latency_up")
            if base and base.get("rps") and cur["rps"] > 3 * base["rps"] and cur["rps"] > 5:
                flags.append("traffic_up")
        if svc in cpu:
            row["cpu_pct"] = _round(cpu[svc], 1)
            if cpu[svc] >= 80:
                flags.append("cpu_high")
        if svc in mem:
            row["memory_mb"] = _round(mem[svc] / 1e6, 1)
            if svc in mem_prev and mem_prev[svc] > 0 and mem[svc] > 1.3 * mem_prev[svc] \
                    and mem[svc] - mem_prev[svc] > 50e6:
                flags.append("memory_growing")
        if states is not None:
            st = states.get(svc)
            row["container_state"] = st["state"] if st else "not_found"
            if not st or st["state"] != "running" or "Restarting" in st["status"]:
                flags.append("container_not_running")
        else:
            row["container_state"] = "unknown (docker unavailable)"
        row["flags"] = flags
        rows.append(row)

    def score(r: Dict[str, Any]) -> float:
        s = 10.0 * len(r["flags"])
        s += 100 * max(0.0, (r.get("error_rate") or 0) - (r.get("baseline_error_rate") or 0))
        if r.get("p95_ms") and r.get("baseline_p95_ms"):
            s += min(20.0, r["p95_ms"] / max(r["baseline_p95_ms"], 1.0))
        return s

    rows.sort(key=score, reverse=True)
    rows = rows[:14]
    for row in rows:
        for key in ("error_rate", "p95_ms", "rps", "cpu_pct", "memory_mb"):
            if row.get(key) is not None:
                evidence.append({"ref": f"metric:{row['service']}:{key}", "kind": "metric", "value": row[key]})
    anomalous = [r["service"] for r in rows if r["flags"]]
    summary = (f"{len(anomalous)} service(s) flagged: {', '.join(anomalous[:5])}" if anomalous
               else "No service crossed the anomaly thresholds in this window.")
    data = {"window": w, "baseline": "same window, 30m earlier", "services": rows}
    if docker_err:
        data["container_state_source"] = f"source_unavailable: {docker_err}"
    return _result(tool, OK, summary, data, evidence)


def get_service_metrics(ctx: ToolContext, service: str, window_minutes: int = 10) -> Dict[str, Any]:
    tool = "get_service_metrics"
    if service in EXCLUDED_SERVICES:
        return _result(tool, ERROR, f"{service} is off-limits (feature-flag service).")
    m = _clamp_window(window_minutes, 10)
    w = f"{m}m"
    sel = f'service_name="{service}"'
    try:
        ops_rate = ctx.prom_vector(
            f"sum by (span_name, span_kind)(rate(traces_span_metrics_calls_total{{{sel}}}[{w}]))")
        ops_err = ctx.prom_vector(
            f'sum by (span_name, span_kind)(rate(traces_span_metrics_calls_total{{{sel},status_code="STATUS_CODE_ERROR"}}[{w}]))')
        ops_p95 = ctx.prom_vector(
            f"histogram_quantile(0.95, sum by (span_name, span_kind, le)"
            f"(rate(traces_span_metrics_duration_milliseconds_bucket{{{sel}}}[{w}])))")
        end = ctx.now()
        start = end - timedelta(minutes=m)
        step = max(15, m * 60 // 20)
        cpu_series = ctx.prometheus.query_range(
            f'avg(container_cpu_utilization_ratio{{container_name="{service}"}})',
            start.timestamp(), end.timestamp(), step)
        mem_series = ctx.prometheus.query_range(
            f'avg(container_memory_usage_total_bytes{{container_name="{service}"}})',
            start.timestamp(), end.timestamp(), step)
    except TelemetryError as e:
        return _result(tool, SOURCE_UNAVAILABLE, f"Prometheus unreachable: {str(e)[:200]}")

    def key(meta: Dict[str, str]) -> Tuple[str, str]:
        return meta.get("span_name", "?"), meta.get("span_kind", "?").replace("SPAN_KIND_", "").lower()

    errs = {key(mt): v for mt, v in ops_err}
    p95s = {key(mt): v for mt, v in ops_p95}
    ops, evidence = [], []
    for meta, rate in ops_rate:
        k = key(meta)
        if _FLAG_NAME.search(k[0]):
            continue
        er = errs.get(k, 0.0) / rate if rate > 0 else 0.0
        ops.append({"operation": k[0], "kind": k[1], "rps": _round(rate, 3), "error_rate": _round(er),
                    "p95_ms": _round(p95s.get(k), 1)})
    ops.sort(key=lambda o: ((o["error_rate"] or 0), (o["p95_ms"] or 0)), reverse=True)
    for o in ops[:10]:
        base = f"metric:{service}:{o['kind']}:{o['operation']}"
        evidence.append({"ref": f"{base}:error_rate", "kind": "metric", "value": o["error_rate"]})
        if o["p95_ms"] is not None:
            evidence.append({"ref": f"{base}:p95_ms", "kind": "metric", "value": o["p95_ms"]})

    data: Dict[str, Any] = {"service": service, "window": w, "operations": ops[:10]}
    for name, series, scale, unit in (("cpu", cpu_series, 1.0, "percent"), ("memory", mem_series, 1e6, "MB")):
        values = [float(v[1]) / scale for r in series.get("data", {}).get("result", []) for v in r.get("values", [])]
        if values:
            trend = {"first": _round(values[0], 3), "last": _round(values[-1], 3),
                     "min": _round(min(values), 3), "max": _round(max(values), 3), "unit": unit,
                     "direction": ("rising" if values[-1] > 1.2 * max(values[0], 1e-9)
                                   else "falling" if values[-1] < 0.8 * values[0] else "flat")}
            data[f"{name}_trend"] = trend
            evidence.append({"ref": f"metric:{service}:{name}_last", "kind": "metric", "value": trend["last"]})
            evidence.append({"ref": f"metric:{service}:{name}_max", "kind": "metric", "value": trend["max"]})
        else:
            data[f"{name}_trend"] = "no_data"

    if not ops and data["cpu_trend"] == "no_data" and data["memory_trend"] == "no_data":
        return _result(tool, NO_DATA, f"No metrics found for service '{service}' in the last {w}.", data)
    worst = ops[0] if ops else None
    summary = (f"{service}: worst operation {worst['operation']} ({worst['kind']}) error_rate="
               f"{worst['error_rate']} p95_ms={worst['p95_ms']}" if worst else f"{service}: no span metrics")
    return _result(tool, OK, summary, data, evidence)


def dependency_map(ctx: ToolContext, service: str) -> Dict[str, Any]:
    tool = "dependency_map"
    if service in EXCLUDED_SERVICES:
        return _result(tool, ERROR, f"{service} is off-limits (feature-flag service).")
    if service not in TOPOLOGY:
        return _result(tool, NO_DATA, f"'{service}' is not in the static demo topology.",
                       {"known_services": sorted(TOPOLOGY)})
    downstream = TOPOLOGY[service]
    upstream = sorted(s for s, callees in TOPOLOGY.items() if service in callees)
    return _result(tool, OK,
                   f"{service} calls {downstream or 'nothing'}; called by {upstream or 'nobody'}.",
                   {"service": service, "calls (downstream)": downstream, "called_by (upstream)": upstream,
                    "source": "static demo topology, not live-observed"})


# --------------------------------------------------------------------------- traces


def _attr_value(v: Dict[str, Any]) -> Any:
    for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if k in v:
            return v[k]
    return None


_KEY_ATTRS = re.compile(
    r"^(http\.(response\.)?status_code|http\.route|http\.method|rpc\.(method|service|grpc\.status_code)"
    r"|db\.system|db\.(operation|statement)|error(\.type)?|exception\.(type|message)|peer\.service"
    r"|server\.address|net\.peer\.name|messaging\.(system|destination\.name|operation)|app\..+)$")


def _parse_spans(raw: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Group a Jaeger v3 OTLP-JSON payload into {trace_id: [compact span]}."""
    traces: Dict[str, List[Dict[str, Any]]] = {}
    for rs in raw.get("result", {}).get("resourceSpans", []) or []:
        svc = JaegerClient._extract_v3_service_name(rs) or "unknown"
        for scope in rs.get("scopeSpans", []) or []:
            for sp in scope.get("spans", []) or []:
                tid = sp.get("traceId")
                if not tid:
                    continue
                attrs = {a.get("key"): _attr_value(a.get("value", {})) for a in sp.get("attributes", []) or []
                         if a.get("key") and not _FLAG_NAME.search(a["key"])}
                status = sp.get("status", {}) or {}
                start = int(sp.get("startTimeUnixNano", 0) or 0)
                end = int(sp.get("endTimeUnixNano", 0) or 0)
                exc = []
                for ev in sp.get("events", []) or []:
                    if _FLAG_NAME.search(ev.get("name", "")):
                        continue
                    if ev.get("name") == "exception":
                        ev_attrs = {a.get("key"): _attr_value(a.get("value", {})) for a in ev.get("attributes", [])}
                        exc.append(str(ev_attrs.get("exception.message") or ev_attrs.get("exception.type"))[:200])
                http_code = attrs.get("http.response.status_code") or attrs.get("http.status_code")
                is_error = JaegerClient._is_v3_span_error(sp) or (
                    str(http_code).isdigit() and int(str(http_code)) >= 500)
                traces.setdefault(tid, []).append({
                    "span_id": sp.get("spanId"), "parent": sp.get("parentSpanId") or None,
                    "service": svc, "name": sp.get("name", ""), "kind": sp.get("kind"),
                    "start": start, "duration_ms": round((end - start) / 1e6, 2) if end and start else None,
                    "error": bool(is_error), "status_message": (status.get("message") or "")[:200] or None,
                    "attributes": {k: v for k, v in attrs.items() if _KEY_ATTRS.match(k)},
                    "exceptions": exc,
                })
    return traces


def _children(spans: List[Dict[str, Any]]) -> Dict[Optional[str], List[Dict[str, Any]]]:
    kids: Dict[Optional[str], List[Dict[str, Any]]] = {}
    ids = {s["span_id"] for s in spans}
    for s in spans:
        parent = s["parent"] if s["parent"] in ids else None
        kids.setdefault(parent, []).append(s)
    return kids


def _deepest_failing(spans: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    kids = _children(spans)
    best: Tuple[int, Optional[Dict[str, Any]]] = (-1, None)

    def walk(span: Dict[str, Any], depth: int) -> None:
        nonlocal best
        if span["error"] and depth > best[0]:
            best = (depth, span)
        for c in kids.get(span["span_id"], []):
            walk(c, depth + 1)

    for root in kids.get(None, []):
        walk(root, 0)
    return best[1]


def _span_brief(s: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not s:
        return None
    brief = {k: s[k] for k in ("span_id", "service", "name", "duration_ms", "status_message") if s.get(k)}
    if s.get("exceptions"):
        brief["exception"] = s["exceptions"][0]
    if s.get("attributes"):
        brief["attributes"] = s["attributes"]
    return brief


# gRPC service names used by the demo, mapped to the service that implements them.
GRPC_SERVICE_OWNER = {
    "AdService": "ad", "CartService": "cart", "CheckoutService": "checkout", "CurrencyService": "currency",
    "EmailService": "email", "PaymentService": "payment", "ProductCatalogService": "product-catalog",
    "RecommendationService": "recommendation", "ShippingService": "shipping", "QuoteService": "quote",
}
# Captures the gRPC service name in "oteldemo.PaymentService/Charge" or "oteldemo.PaymentService".
_GRPC_NAME = re.compile(r"(?:^|\.)(\w+Service)(?:/|$)")
SPAN_KIND_CLIENT = 3


def _callee_of(span: Dict[str, Any]) -> Optional[str]:
    """Which demo service or infra component a client span calls, if it can be told."""
    attrs = span.get("attributes") or {}
    for text in (attrs.get("rpc.service"), attrs.get("rpc.method"), span.get("name")):
        m = _GRPC_NAME.search(str(text or ""))
        if m and m.group(1) in GRPC_SERVICE_OWNER:
            return GRPC_SERVICE_OWNER[m.group(1)]
    for key in ("peer.service", "server.address", "net.peer.name"):
        host = str(attrs.get(key) or "").split(":")[0]
        if host in TOPOLOGY:
            return host
    db = str(attrs.get("db.system") or "").lower()
    if db in ("redis", "valkey"):
        return "valkey-cart"
    if db in ("postgresql", "postgres"):
        return "astronomy-db"
    if str(attrs.get("messaging.system") or "").lower() == "kafka":
        return "kafka"
    return None


def _dependency_failure(span: Optional[Dict[str, Any]], spans: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """If the failing span is a client call whose callee never produced a span, the call never
    reached the callee: the callee is unreachable from the caller's point of view."""
    if not span or not span["error"] or span.get("kind") != SPAN_KIND_CLIENT:
        return None
    callee = _callee_of(span)
    if not callee or callee == span["service"]:
        return None
    kids = _children(spans).get(span["span_id"], [])
    reached = any(k["service"] == callee for k in kids)
    return {"caller": span["service"], "dependency": callee, "reached": reached,
            "operation": span["name"], "error": span.get("status_message") or (span.get("exceptions") or [None])[0],
            "span_id": span["span_id"]}


def _window_params(ctx: ToolContext, minutes: int) -> Tuple[datetime, datetime]:
    end = ctx.now()
    return end - timedelta(minutes=minutes), end


def search_traces(ctx: ToolContext, service: str, errors_only: bool = True,
                  min_duration_ms: Optional[int] = None, window_minutes: int = 10,
                  limit: int = 8) -> Dict[str, Any]:
    tool = "search_traces"
    if service in EXCLUDED_SERVICES:
        return _result(tool, ERROR, f"{service} is off-limits (feature-flag service).")
    m = _clamp_window(window_minutes, 10)
    limit = max(1, min(15, int(limit or 8)))
    start, end = _window_params(ctx, m)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    params: Dict[str, Any] = {
        "query.service_name": service,
        "query.num_traces": limit * 2,
        "query.start_time_min": start.strftime(fmt),
        "query.start_time_max": end.strftime(fmt),
    }
    if min_duration_ms:
        params["query.duration_min"] = f"{int(min_duration_ms)}ms"

    def fetch(extra: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        try:
            return _parse_spans(ctx.jaeger._request("GET", "/jaeger/ui/api/v3/traces", params={**params, **extra}))
        except TelemetryError as e:
            if getattr(e, "status_code", None) == 404:
                return {}
            raise

    try:
        if errors_only:
            # Jaeger matches error spans server-side; the unfiltered scan of the newest traces
            # is a fallback in case some failing spans carry an error status but no error tag.
            traces = fetch({"query.attributes": json.dumps({"error": "true"}), "query.num_traces": 30})
            if not any(s["error"] for spans in traces.values() for s in spans):
                traces = fetch({"query.num_traces": 60})
        else:
            traces = fetch({})
    except TelemetryError as e:
        return _result(tool, SOURCE_UNAVAILABLE, f"Jaeger unreachable: {str(e)[:200]}")
    if not traces:
        return _result(tool, NO_DATA, f"Jaeger found no traces for '{service}' in the last {m}m.")
    rows, evidence = [], []
    for tid, spans in traces.items():
        errors = [s for s in spans if s["error"]]
        if errors_only and not errors:
            continue
        kids = _children(spans)
        roots = kids.get(None, [])
        root = min(roots, key=lambda s: s["start"]) if roots else min(spans, key=lambda s: s["start"])
        deepest = _deepest_failing(spans)
        row = {
            "trace_id": tid, "root": f"{root['service']}: {root['name']}", "duration_ms": root["duration_ms"],
            "span_count": len(spans), "error_span_count": len(errors),
            "error_services": sorted({s["service"] for s in errors}),
            "deepest_failing_span": _span_brief(deepest),
        }
        dep = _dependency_failure(deepest, spans)
        if dep:
            row["dependency_failure"] = dep
        rows.append(row)
    rows.sort(key=lambda r: (r["error_span_count"] > 0, r["duration_ms"] or 0), reverse=True)
    rows = rows[:limit]
    for r in rows:
        evidence.append({"ref": r["trace_id"], "kind": "trace", "service": service,
                         "has_error": r["error_span_count"] > 0})
        dep = r.get("dependency_failure")
        if dep:
            evidence.append({"ref": f"span:{r['trace_id']}:{dep['span_id']}", "kind": "trace",
                             "service": dep["caller"], "caller": dep["caller"],
                             "dependency": dep["dependency"], "reached": dep["reached"]})
    if not rows:
        what = "error traces" if errors_only else "traces"
        return _result(tool, NO_DATA, f"No {what} for '{service}' in the last {m}m "
                       f"({len(traces)} traces scanned).", {"traces_scanned": len(traces)})
    summary = f"{len(rows)} trace(s) for {service}"
    if errors_only:
        deepest = [r["deepest_failing_span"] for r in rows if r["deepest_failing_span"]]
        if deepest:
            summary += f"; deepest failing span e.g. {deepest[0]['service']}: {deepest[0]['name']}"
        unreached = sorted({(r["dependency_failure"]["caller"], r["dependency_failure"]["dependency"])
                            for r in rows if r.get("dependency_failure") and not r["dependency_failure"]["reached"]})
        for caller, dep_svc in unreached:
            summary += f"; {caller}'s calls to {dep_svc} never reached {dep_svc}"
    return _result(tool, OK, summary, {"window": f"{m}m", "traces_scanned": len(traces), "traces": rows},
                   evidence)


def get_trace(ctx: ToolContext, trace_id: str) -> Dict[str, Any]:
    tool = "get_trace"
    tid = (trace_id or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{16,32}", tid):
        return _result(tool, ERROR, "trace_id must be a 16-32 character hex string.")
    try:
        raw = ctx.jaeger._request("GET", f"/jaeger/ui/api/v3/traces/{tid}")
    except TelemetryError as e:
        if getattr(e, "status_code", None) == 404:
            return _result(tool, NO_DATA, f"Trace {tid} not found in Jaeger.")
        return _result(tool, SOURCE_UNAVAILABLE, f"Jaeger unreachable: {str(e)[:200]}")
    spans = _parse_spans(raw).get(tid) or next(iter(_parse_spans(raw).values()), [])
    spans = [s for s in spans if s["service"] not in EXCLUDED_SERVICES]
    if not spans:
        return _result(tool, NO_DATA, f"Trace {tid} has no spans.")

    kids = _children(spans)
    ordered: List[Dict[str, Any]] = []

    def walk(span: Dict[str, Any], depth: int) -> None:
        child_ms = sum((c["duration_ms"] or 0) for c in kids.get(span["span_id"], []))
        entry = {"depth": depth, **_span_brief(span), "error": span["error"],
                 "self_ms": round(max(0.0, (span["duration_ms"] or 0) - child_ms), 2)}
        ordered.append(entry)
        for c in sorted(kids.get(span["span_id"], []), key=lambda s: s["start"]):
            walk(c, depth + 1)

    for root in sorted(kids.get(None, []), key=lambda s: s["start"]):
        walk(root, 0)

    error_ids = {s["span_id"] for s in spans if s["error"]}
    by_id = {s["span_id"]: s for s in spans}
    keep = set(error_ids)
    for sid in list(error_ids):  # keep ancestors of failing spans for context
        p = by_id[sid]["parent"]
        while p in by_id and p not in keep:
            keep.add(p)
            p = by_id[p]["parent"]
    slowest = sorted(ordered, key=lambda e: e["self_ms"], reverse=True)[:5]
    keep |= {e["span_id"] for e in slowest}
    shown = [e for e in ordered if e["span_id"] in keep or e["depth"] <= 1][:40]

    deepest = _deepest_failing(spans)
    dep = _dependency_failure(deepest, spans)
    evidence = [{"ref": tid, "kind": "trace", "has_error": bool(error_ids)}]
    if deepest:
        ev = {"ref": f"span:{tid}:{deepest['span_id']}", "kind": "trace",
              "service": deepest["service"], "name": deepest["name"]}
        if dep:
            ev.update(caller=dep["caller"], dependency=dep["dependency"], reached=dep["reached"])
        evidence.append(ev)
    data = {"trace_id": tid, "span_count": len(spans), "error_span_count": len(error_ids),
            "services": sorted({s["service"] for s in spans}),
            "deepest_failing_span": _span_brief(deepest),
            **({"dependency_failure": dep} if dep else {}),
            "largest_self_time": [{k: e.get(k) for k in ("service", "name", "self_ms")} for e in slowest[:3]],
            "spans": shown}
    summary = (f"{len(spans)} spans, {len(error_ids)} failing; deepest failure "
               f"{deepest['service']}: {deepest['name']}" + (
                   f" (call from {dep['caller']} never reached {dep['dependency']})"
                   if dep and not dep["reached"] else "") if deepest
               else f"{len(spans)} spans, no failing spans; slowest self-time "
                    f"{slowest[0]['service']}: {slowest[0]['name']} ({slowest[0]['self_ms']} ms)")
    return _result(tool, OK, summary, data, evidence)


# --------------------------------------------------------------------------- logs

_LEVELS = {
    "error": (17, ["error", "ERROR", "Error", "fatal", "FATAL", "Fatal", "critical", "CRITICAL", "Critical"]),
    "warn": (13, ["warn", "WARN", "Warn", "warning", "WARNING", "Warning"]),
}


def search_logs(ctx: ToolContext, service: Optional[str] = None, level: str = "error",
                text: Optional[str] = None, window_minutes: int = 10, limit: int = 15) -> Dict[str, Any]:
    tool = "search_logs"
    if service in EXCLUDED_SERVICES:
        return _result(tool, ERROR, f"{service} is off-limits (feature-flag service).")
    m = _clamp_window(window_minutes, 10)
    limit = max(1, min(30, int(limit or 15)))
    filters: List[Dict[str, Any]] = [{"range": {"observedTimestamp": {"gte": f"now-{m}m"}}}]
    if service:
        filters.append({"term": {"resource.service.name.keyword": service}})
    level = (level or "any").lower()
    if level in ("error", "warn"):
        min_num = _LEVELS[level][0]
        names = _LEVELS["error"][1] + (_LEVELS["warn"][1] if level == "warn" else [])
        filters.append({"bool": {"should": [{"range": {"severity.number": {"gte": min_num}}},
                                            {"terms": {"severity.text.keyword": names}}],
                                 "minimum_should_match": 1}})
    if text:
        filters.append({"match_phrase": {"body": str(text)[:200]}})
    dsl = {
        "size": limit,
        "sort": [{"observedTimestamp": {"order": "desc"}}],
        "_source": ["observedTimestamp", "severity.text", "body", "traceId", "resource.service.name"],
        "query": {"bool": {"filter": filters,
                           "must_not": [{"terms": {"resource.service.name.keyword": sorted(EXCLUDED_SERVICES)}}]}},
        "aggs": {"by_service": {"terms": {"field": "resource.service.name.keyword", "size": 10}}},
    }
    try:
        res = ctx.opensearch.search(index="otel-logs-*", query_dsl=dsl)
    except TelemetryError as e:
        return _result(tool, SOURCE_UNAVAILABLE, f"OpenSearch unreachable: {str(e)[:200]}")

    hits = res.get("hits", {})
    total = hits.get("total", {})
    total = total.get("value") if isinstance(total, dict) else total
    lines, evidence = [], []
    for h in hits.get("hits", []):
        src = h.get("_source", {})
        body = src.get("body")
        body = str(body.get("stringValue") if isinstance(body, dict) else body or "").strip()
        if _FLAG_NAME.search(body):
            continue
        sev = src.get("severity", {})
        svc = (src.get("resource", {}) or {}).get("service.name") or (
            (src.get("resource", {}).get("service") or {}).get("name") if isinstance(
                src.get("resource", {}).get("service"), dict) else None)
        ref = f"log:{h.get('_id')}"
        line = {"ref": ref, "ts": src.get("observedTimestamp"), "service": svc,
                "severity": sev.get("text") if isinstance(sev, dict) else sev,
                "body": body[:300], "trace_id": src.get("traceId") or None}
        lines.append(line)
        evidence.append({"ref": ref, "kind": "log", "service": svc, "text": body[:300],
                         "trace_id": line["trace_id"]})
        if line["trace_id"]:
            evidence.append({"ref": line["trace_id"], "kind": "trace", "service": svc, "via": ref})
    by_service = {b["key"]: b["doc_count"] for b in res.get("aggregations", {}).get("by_service", {})
                  .get("buckets", []) if b["key"] not in EXCLUDED_SERVICES}
    scope = f"{level} logs" + (f" for {service}" if service else "") + (f" matching '{text}'" if text else "")
    if not lines:
        return _result(tool, NO_DATA, f"No {scope} in the last {m}m.", {"total_matches": total or 0})
    return _result(tool, OK, f"{total} {scope} in the last {m}m; showing {len(lines)} newest.",
                   {"window": f"{m}m", "total_matches": total, "matches_by_service": by_service,
                    "lines": lines}, evidence)


# --------------------------------------------------------------------------- containers


def container_health(ctx: ToolContext, service: Optional[str] = None) -> Dict[str, Any]:
    tool = "container_health"
    if service in EXCLUDED_SERVICES:
        return _result(tool, ERROR, f"{service} is off-limits (feature-flag service).")
    try:
        if service:
            names = [service]
        else:
            names = _scoped_container_names(ctx)
        if not names:
            return _result(tool, NO_DATA, "No monitored demo containers found.", {"containers": []}, [])
        raw = ctx.docker(["inspect", *names])
        info = json.loads(raw)
    except Exception as e:
        msg = str(e)[:200]
        if service and "no such object" in msg.lower():
            return _result(tool, OK, f"Container '{service}' does not exist.",
                           {"containers": [{"name": service, "state": "missing"}]},
                           [{"ref": f"container:{service}:state", "kind": "container", "value": "missing"}])
        return _result(tool, SOURCE_UNAVAILABLE, f"Docker unavailable: {msg}")

    proj = _discover_compose_project(ctx)
    if service:
        c_info = info[0] if info else {}
        c_labels = (c_info.get("Config", {}) or {}).get("Labels", {}) or {}
        c_proj = _extract_compose_project(c_labels)
        is_demo = False
        if proj:
            if c_proj == proj:
                is_demo = True
        else:
            if c_proj in ("opentelemetry-demo", "opentelemetry_demo", "otel-demo"):
                is_demo = True
            elif not c_proj and service in DEMO_CONTAINERS:
                is_demo = True
        if not is_demo:
            return _result(tool, OK, f"Container '{service}' is not part of the OpenTelemetry Demo.",
                           {"containers": []}, [])
    else:
        verified_info = []
        for c in info:
            c_labels = (c.get("Config", {}) or {}).get("Labels", {}) or {}
            c_proj = _extract_compose_project(c_labels)
            c_name = c.get("Name", "").lstrip("/")
            if proj:
                if c_proj == proj and c_name in DEMO_CONTAINERS:
                    verified_info.append(c)
            else:
                if (c_proj in ("opentelemetry-demo", "opentelemetry_demo", "otel-demo") or not c_proj) and c_name in DEMO_CONTAINERS:
                    verified_info.append(c)
        info = verified_info
        if not info:
            return _result(tool, NO_DATA, "No monitored demo containers found.", {"containers": []}, [])

    try:
        cpu = ctx.prom_by("avg by (container_name)(avg_over_time(container_cpu_utilization_ratio[5m]))",
                          "container_name")
        mem = ctx.prom_by("avg by (container_name)(container_memory_usage_total_bytes)", "container_name")
        limit = ctx.prom_by("avg by (container_name)(container_memory_usage_limit_bytes)", "container_name")
        metrics_note = None
    except TelemetryError as e:
        cpu, mem, limit, metrics_note = {}, {}, {}, f"source_unavailable: {str(e)[:120]}"

    rows, evidence = [], []
    for c in info:
        name = c.get("Name", "").lstrip("/")
        st = c.get("State", {}) or {}
        row = {"name": name, "state": st.get("Status"), "restart_count": c.get("RestartCount"),
               "exit_code": st.get("ExitCode"), "oom_killed": st.get("OOMKilled"),
               "health": (st.get("Health") or {}).get("Status"), "started_at": st.get("StartedAt")}
        if name in cpu:
            row["cpu_pct_5m"] = _round(cpu[name], 1)
        if name in mem:
            row["memory_mb"] = _round(mem[name] / 1e6, 1)
            if limit.get(name):
                row["memory_pct_of_limit"] = _round(100 * mem[name] / limit[name], 1)
        rows.append(row)
        for k in ("state", "restart_count", "exit_code", "oom_killed", "health", "cpu_pct_5m", "memory_mb"):
            if row.get(k) is not None:
                evidence.append({"ref": f"container:{name}:{k}", "kind": "container", "value": row[k]})

    def bad(r: Dict[str, Any]) -> bool:
        return (r["state"] != "running" or (r["restart_count"] or 0) > 0 or r["oom_killed"]
                or r["health"] == "unhealthy")

    rows.sort(key=lambda r: (bad(r), r.get("cpu_pct_5m") or 0), reverse=True)
    unhealthy = [r["name"] for r in rows if bad(r)]
    summary = (f"Unhealthy/restarted: {', '.join(unhealthy)}" if unhealthy
               else f"All {len(rows)} inspected container(s) running with 0 restarts.")
    if service:
        data: Dict[str, Any] = {"containers": rows}
    else:
        # Full detail for unhealthy containers and the busiest few; the rest are listed by name.
        detailed = [r for r in rows if bad(r)] + [r for r in rows if not bad(r)][:5]
        names = {r["name"] for r in detailed}
        data = {"containers": detailed,
                "other_running_healthy": sorted(r["name"] for r in rows if r["name"] not in names)}
        evidence = [e for e in evidence if e["ref"].split(":")[1] in names
                    or e["ref"].endswith((":state", ":restart_count"))]
    if metrics_note:
        data["metrics"] = metrics_note
    return _result(tool, OK, summary, data, evidence)


def deploy_history(ctx: ToolContext) -> Dict[str, Any]:
    return _result("deploy_history", SOURCE_UNAVAILABLE,
                   "No deployment-history source is available (the organisers have not provided one).",
                   {"available": False})


# --------------------------------------------------------------------------- registry

_WINDOW = {"type": "integer", "minimum": 1, "maximum": 60, "description": "Look-back window in minutes."}

TOOL_SPECS: List[Dict[str, Any]] = [
    {"name": "system_overview",
     "description": "Per-service request rate, error rate, p95 latency (vs the same window 30m earlier), "
                    "container CPU/memory and container state, most anomalous first. Start here.",
     "parameters": {"type": "object", "properties": {"window_minutes": _WINDOW},
                    "required": [], "additionalProperties": False}},
    {"name": "get_service_metrics",
     "description": "Per-operation error rate and p95 latency for one service (server, client and consumer "
                    "spans), plus CPU and memory trend over the window.",
     "parameters": {"type": "object", "properties": {"service": {"type": "string"}, "window_minutes": _WINDOW},
                    "required": ["service"], "additionalProperties": False}},
    {"name": "dependency_map",
     "description": "Upstream callers and downstream dependencies of a service (static demo topology).",
     "parameters": {"type": "object", "properties": {"service": {"type": "string"}},
                    "required": ["service"], "additionalProperties": False}},
    {"name": "search_traces",
     "description": "Find recent traces through a service. Returns trace IDs, root span, duration and the "
                    "deepest failing span of each. errors_only defaults to true.",
     "parameters": {"type": "object", "properties": {
         "service": {"type": "string"}, "errors_only": {"type": "boolean"},
         "min_duration_ms": {"type": "integer", "minimum": 1}, "window_minutes": _WINDOW,
         "limit": {"type": "integer", "minimum": 1, "maximum": 15}},
         "required": ["service"], "additionalProperties": False}},
    {"name": "get_trace",
     "description": "Compact span tree for one trace ID: failing spans with their ancestors, the deepest "
                    "failing span, exceptions, key attributes and the spans with the largest self-time.",
     "parameters": {"type": "object", "properties": {"trace_id": {"type": "string"}},
                    "required": ["trace_id"], "additionalProperties": False}},
    {"name": "search_logs",
     "description": "Recent log lines (newest first) with timestamp, severity, service and trace ID. "
                    "level is 'error' (default), 'warn' (warn and above) or 'any'. Omit service to search all.",
     "parameters": {"type": "object", "properties": {
         "service": {"type": "string"}, "level": {"type": "string", "enum": ["error", "warn", "any"]},
         "text": {"type": "string"}, "window_minutes": _WINDOW,
         "limit": {"type": "integer", "minimum": 1, "maximum": 30}},
         "required": [], "additionalProperties": False}},
    {"name": "container_health",
     "description": "Container state, restart count, exit code, OOM-killed flag, health, CPU and memory. "
                    "Omit service to list all containers, unhealthy first.",
     "parameters": {"type": "object", "properties": {"service": {"type": "string"}},
                    "required": [], "additionalProperties": False}},
    {"name": "deploy_history",
     "description": "Recent deployments. Currently has no data source and reports source_unavailable.",
     "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}},
]

_IMPLS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "system_overview": system_overview,
    "get_service_metrics": get_service_metrics,
    "dependency_map": dependency_map,
    "search_traces": search_traces,
    "get_trace": get_trace,
    "search_logs": search_logs,
    "container_health": container_health,
    "deploy_history": deploy_history,
}


class ToolBox:
    """Validates arguments, runs a tool and post-processes its result."""

    def __init__(self, ctx: Optional[ToolContext] = None,
                 impls: Optional[Dict[str, Callable[..., Dict[str, Any]]]] = None,
                 specs: Optional[List[Dict[str, Any]]] = None) -> None:
        self.ctx = ctx or ToolContext()
        self.impls = impls or _IMPLS
        self.specs = specs or [s for s in TOOL_SPECS if s["name"] in self.impls]
        self._schemas = {s["name"]: s["parameters"] for s in self.specs}

    @property
    def names(self) -> List[str]:
        return [s["name"] for s in self.specs]

    def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._schemas:
            return _result(name, ERROR, f"Unknown tool '{name}'. Allowed: {', '.join(self.names)}.")
        try:
            jsonschema.validate(arguments, self._schemas[name])
        except jsonschema.ValidationError as e:
            return _result(name, ERROR, f"Invalid arguments: {e.message}")
        try:
            res = self.impls[name](self.ctx, **arguments)
        except Exception as e:  # a tool crash is reported, never treated as healthy
            res = _result(name, ERROR, f"Tool failed: {type(e).__name__}: {str(e)[:200]}")
        return cap_result(strip_flag_data(res))
