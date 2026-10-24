"""The agent's tools: one registry used by the LLM (as function-calling specs), by the deterministic
fallback investigator, by `see`, and by the evidence verifier.

Every call goes through Session.call(), which
  * caches identical calls,
  * never raises (a failing tool returns {"error": ...} so the agent can say what it could not see),
  * records name / args / result / duration -> runs/<id>/tool_calls.jsonl (the audit trail),
  * keeps the raw text of every observation so cited evidence can be checked against it.

Backends: "live" (Prometheus / Jaeger / OpenSearch / Docker) or "replay" (a recorded snapshot file,
used for offline bundles and tests).
"""
import json
import time

from agent import config, memory, topology
from agent.tools import deploys, logs, metrics, traces


def _health():
    h = metrics.service_health()
    return {"window": config.WINDOW, "baseline_offset": config.BASELINE_OFFSET,
            "anomalies": metrics.anomalies(h),
            "services": {s: v for s, v in h.items()
                         if v["error_rate"] > 0 or v["p95_ms"] > 1.5 * max(v["p95_ms_baseline"], 1)
                         or v["req_per_s"] < 0.5 * v["req_per_s_baseline"]},
            "healthy_services": sorted(s for s, v in h.items() if v["error_rate"] == 0
                                       and v["p95_ms"] <= 1.5 * max(v["p95_ms_baseline"], 1)
                                       and v["req_per_s"] >= 0.5 * v["req_per_s_baseline"])}


def _deps(service: str):
    return {"service": service, "calls (downstream)": topology.callees(service),
            "called_by (upstream)": topology.callers(service),
            "is_infra": service in topology.INFRA}


# name -> (function, description, JSON-schema properties, required)
TOOLS = {
    "get_service_health": (
        lambda: _health(),
        "START HERE. Per-service request rate, error rate and p95 latency now vs a baseline 30 min ago, "
        "plus a list of anomalies. Shows which services look unhealthy (symptoms, not yet root cause).",
        {}, []),
    "get_failing_operations": (
        lambda: metrics.top_error_operations(),
        "Top failing operations (span names) by error rate across all services.", {}, []),
    "get_error_origins": (
        lambda service=None: traces.error_origins(service=service),
        "From traces: spans where errors ORIGINATE (error span with no failing child), with messages, "
        "the peer being called and example trace IDs. Optional: restrict to one service.",
        {"service": {"type": "string", "description": "optional service name"}}, []),
    "get_slow_operations": (
        lambda service=None: traces.slow_operations(service=service),
        "From traces: operations with the highest SELF time (time not spent in children) -> where latency "
        "is really spent. Optional: one service.",
        {"service": {"type": "string"}}, []),
    "get_trace": (
        lambda trace_id: traces.get_trace(trace_id),
        "Full call tree of one trace (use a trace ID returned by another tool).",
        {"trace_id": {"type": "string"}}, ["trace_id"]),
    "get_service_detail": (
        lambda service: metrics.service_detail(service),
        "Per-operation metrics of ONE service (rate, error rate, p95 now vs baseline).",
        {"service": {"type": "string"}}, ["service"]),
    "get_error_log_summary": (
        lambda: logs.error_summary(topology.APP_CONTAINERS),
        "Error-log templates per service in the window (counts + top messages).", {}, []),
    "search_logs": (
        lambda service, contains="": logs.search_logs(service, contains=contains),
        "Exact recent error log lines of ONE service (optionally containing a substring). Quote these.",
        {"service": {"type": "string"}, "contains": {"type": "string"}}, ["service"]),
    "get_runtime_events": (
        lambda: deploys.analyse(),
        "Container facts that differ from normal: stopped/exited, restarts, OOM kills, unhealthy, "
        "CPU/memory far above the healthy baseline.", {}, []),
    "get_container_health": (
        lambda service: deploys.container_health(service),
        "Docker state of ONE container: status, restarts, OOM, health, CPU/memory vs baseline, limits.",
        {"service": {"type": "string"}}, ["service"]),
    "get_deploy_history": (
        lambda: deploys.deploy_history(),
        "Containers created or (re)started in the last 60 min (the 'deploy history' of this demo).", {}, []),
    "get_dependencies": (
        lambda service: _deps(service),
        "Who this service calls and who calls it (static architecture graph).",
        {"service": {"type": "string"}}, ["service"]),
    "query_prometheus": (
        lambda promql: metrics.query(promql),
        "Read-only PromQL for anything not covered above (e.g. kafka consumer lag, JVM GC, process memory).",
        {"promql": {"type": "string"}}, ["promql"]),
    "similar_past_incidents": (
        lambda services: memory.similar(services),
        "Earlier incident reports from this agent whose suspected services overlap (incident memory). "
        "A hint only - the current telemetry must still support the diagnosis.",
        {"services": {"type": "array", "items": {"type": "string"}}}, ["services"]),
}


def llm_specs(extra: list = ()) -> list:
    specs = [{"type": "function", "function": {
        "name": n, "description": d,
        "parameters": {"type": "object", "properties": p, "required": r}}}
        for n, (_, d, p, r) in TOOLS.items()]
    return specs + list(extra)


class Session:
    def __init__(self, incident_dir=None, replay: dict = None):
        self.dir = incident_dir
        self.replay = replay          # {"calls": [{"name","args","result"}...]} for offline runs
        self.calls = []
        self._cache = {}

    def _key(self, name, args):
        return name + "|" + json.dumps(args or {}, sort_keys=True)

    def _from_replay(self, name, args):
        calls = self.replay.get("calls", [])
        for c in calls:
            if c["name"] == name and (c.get("args") or {}) == (args or {}):
                return c["result"]
        for c in calls:  # same tool, other args -> better than nothing for no-arg tools only
            if c["name"] == name and not args:
                return c["result"]
        return {"error": f"{name}({args}) not in recorded bundle"}

    def call(self, name: str, args: dict = None) -> dict:
        args = {k: v for k, v in (args or {}).items() if v not in (None, "")}
        key = self._key(name, args)
        if key in self._cache:
            return self._cache[key]
        t = time.time()
        if name not in TOOLS:
            res = {"error": f"unknown tool {name}; available: {sorted(TOOLS)}"}
        elif self.replay is not None:
            res = self._from_replay(name, args)
        else:
            try:
                res = TOOLS[name][0](**args)
            except TypeError as e:
                res = {"error": f"bad arguments: {e}"}
            except Exception as e:  # a broken data source must not crash the agent
                res = {"error": f"{type(e).__name__}: {str(e)[:250]}"}
        rec = {"n": len(self.calls) + 1, "name": name, "args": args, "secs": round(time.time() - t, 2),
               "ok": not (isinstance(res, dict) and "error" in res), "result": res}
        self.calls.append(rec)
        self._cache[key] = res
        if self.dir:
            with open(self.dir / "tool_calls.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str) + "\n")
        return res

    def corpus(self) -> str:
        """All observed data as text (used to verify that cited evidence really exists)."""
        return "\n".join(json.dumps(c["result"], default=str) for c in self.calls)

    def snapshot(self) -> dict:
        return {"recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "calls": [{"name": c["name"], "args": c["args"], "result": c["result"]} for c in self.calls]}


def short(res, limit=3500) -> str:
    s = json.dumps(res, default=str, separators=(",", ":"))
    return s if len(s) <= limit else s[:limit] + f'..."(truncated {len(s) - limit} chars)"'
