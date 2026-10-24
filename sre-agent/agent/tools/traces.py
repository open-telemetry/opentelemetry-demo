"""EYES / traces from Jaeger (read-only). Uses the OTLP-shaped v3 API, falls back to the classic v1 API.

Key idea: an error span whose children are all OK is where the error ORIGINATES. Upstream spans that
fail only because a child failed are victims. Every finding carries real trace IDs as evidence.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import requests

from agent import config


def _secs(lookback: str) -> int:
    amount = int("".join(c for c in lookback if c.isdigit()) or "5")
    unit = "".join(c for c in lookback if c.isalpha()).lower() or "m"
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(unit, 60)


def _get(path: str, params: dict = None) -> dict:
    r = requests.get(f"{config.JAEGER_URL}/api/{path}", params=params, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


def services() -> list:
    try:
        p = _get("v3/services")
        names = p.get("services") or p.get("data") or []
    except requests.RequestException:
        names = _get("services").get("data") or []
    return sorted(s for s in names if not s.startswith("jaeger"))


def _val(v):
    if not isinstance(v, dict):
        return v
    for k in ("stringValue", "intValue", "boolValue", "doubleValue", "bytesValue", "arrayValue", "kvlistValue"):
        if k in v:
            return v[k]
    return v


def _attrs(items) -> dict:
    return {i["key"]: _val(i.get("value")) for i in items or [] if "key" in i}


def _flatten_v3(payload: dict, only_service: str = None) -> list:
    result = payload.get("result", payload)
    spans = []
    for rg in result.get("resourceSpans", []):
        svc = _attrs(rg.get("resource", {}).get("attributes", [])).get("service.name", "?")
        if only_service and svc != only_service:
            continue
        for sg in rg.get("scopeSpans", []):
            for s in sg.get("spans", []):
                st = s.get("status", {}) or {}
                code = st.get("code", 0)
                code = {"STATUS_CODE_ERROR": 2, "STATUS_CODE_OK": 1, "STATUS_CODE_UNSET": 0}.get(code, code)
                start, end = int(s.get("startTimeUnixNano", 0) or 0), int(s.get("endTimeUnixNano", 0) or 0)
                spans.append({"traceID": s.get("traceId", ""), "spanID": s.get("spanId", ""),
                              "parentSpanID": s.get("parentSpanId", ""), "service": svc,
                              "operation": s.get("name", ""), "start": start,
                              "duration_us": max(0, end - start) // 1000, "status_code": code,
                              "status_message": st.get("message", ""), "attrs": _attrs(s.get("attributes"))})
    return spans


def _flatten_v1(traces: list, only_service: str = None) -> list:
    spans = []
    for t in traces:
        procs = {k: v.get("serviceName") for k, v in t.get("processes", {}).items()}
        for s in t.get("spans", []):
            svc = procs.get(s.get("processID"), "?")
            if only_service and svc != only_service:
                continue
            tags = {x["key"]: x.get("value") for x in s.get("tags", [])}
            parent = next((r["spanID"] for r in s.get("references", []) if r.get("refType") == "CHILD_OF"), "")
            code = 2 if tags.get("error") in (True, "true") or tags.get("otel.status_code") == "ERROR" else 0
            spans.append({"traceID": s.get("traceID", ""), "spanID": s.get("spanID", ""), "parentSpanID": parent,
                          "service": svc, "operation": s.get("operationName", ""), "start": s.get("startTime", 0),
                          "duration_us": s.get("duration", 0), "status_code": code,
                          "status_message": tags.get("otel.status_description", ""), "attrs": tags})
    return spans


def _fetch(service: str, lookback: str, limit: int, only_service: bool = False) -> list:
    end = datetime.now(timezone.utc)
    start = end - timedelta(seconds=_secs(lookback))
    fmt = lambda d: d.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    try:
        p = _get("v3/traces", {"query.serviceName": service, "query.startTimeMin": fmt(start),
                               "query.startTimeMax": fmt(end), "query.searchDepth": str(limit)})
        return _flatten_v3(p, service if only_service else None)
    except requests.RequestException:
        p = _get("traces", {"service": service, "lookback": lookback, "limit": limit})
        return _flatten_v1(p.get("data") or [], service if only_service else None)


def _collect(svcs: list, lookback: str, limit: int) -> tuple:
    """Fetch traces per service and MERGE all spans of those traces (all services), deduplicated.
    Keeping other services' spans is essential: a caller's client span is only a 'victim' if we can
    see the callee's failing child span."""
    spans, failed = {}, []
    for svc in svcs:
        try:
            for s in _fetch(svc, lookback, limit):
                spans[(s["traceID"], s["spanID"])] = s
        except requests.RequestException as e:
            failed.append(f"{svc}: {type(e).__name__}")
    return list(spans.values()), failed


def _is_error(s: dict) -> bool:
    if s["status_code"] == 2:
        return True
    a = s["attrs"]
    try:
        if a.get("http.response.status_code") is not None and int(a["http.response.status_code"]) >= 500:
            return True
        if a.get("rpc.grpc.status_code") is not None and int(a["rpc.grpc.status_code"]) not in (0, 1):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _msg(s: dict) -> str:
    for k in ("exception.message", "error.message", "error.type"):
        if s["attrs"].get(k):
            return str(s["attrs"][k])[:200]
    if s.get("status_message"):
        return str(s["status_message"])[:200]
    for k in ("rpc.grpc.status_code", "http.response.status_code"):
        if s["attrs"].get(k) is not None:
            return f"{k}={s['attrs'][k]}"
    return ""


def _peer(s: dict) -> str:
    a = s["attrs"]
    return str(a.get("rpc.service") or a.get("server.address") or a.get("net.peer.name")
               or a.get("db.system") or a.get("messaging.destination.name") or "")


def error_origins(lookback: str = None, per_service_limit: int = 30, service: str = None) -> dict:
    """Where errors START. Returns origin spans with counts, messages and example trace IDs."""
    lookback = lookback or config.WINDOW
    svcs = [service] if service else services()
    origins, msgs, ids, peers = Counter(), defaultdict(Counter), defaultdict(list), defaultdict(Counter)
    err_by_svc = Counter()
    spans, failed = _collect(svcs, lookback, per_service_limit)
    by_id = {(s["traceID"], s["spanID"]): s for s in spans}
    kids = defaultdict(list)
    for s in spans:
        if (s["traceID"], s["parentSpanID"]) in by_id:
            kids[(s["traceID"], s["parentSpanID"])].append((s["traceID"], s["spanID"]))
    traces_seen = {s["traceID"] for s in spans}
    for s in spans:
        if service and s["service"] != service:
            continue
        if not _is_error(s):
            continue
        err_by_svc[s["service"]] += 1
        if any(_is_error(by_id[c]) for c in kids[(s["traceID"], s["spanID"])]):
            continue  # a child failed first -> this span is a victim
        key = f"{s['service']} :: {s['operation']}"
        origins[key] += 1
        if _msg(s):
            msgs[key][_msg(s)] += 1
        if _peer(s):
            peers[key][_peer(s)] += 1
        if len(ids[key]) < 3 and s["traceID"] not in ids[key]:
            ids[key].append(s["traceID"])
    return {
        "lookback": lookback, "traces_sampled": len(traces_seen),
        "error_spans_by_service": dict(err_by_svc.most_common(10)),
        "error_origins": [{"where": k, "count": n, "top_messages": [m for m, _ in msgs[k].most_common(2)],
                           "calls_to": [p for p, _ in peers[k].most_common(2)],
                           "example_trace_ids": ids[k]} for k, n in origins.most_common(8)],
        "services_not_readable": failed,
    }


def slow_operations(service: str = None, lookback: str = None, limit: int = 30, top: int = 8) -> dict:
    """Slowest operations (self time ~ duration minus children) -> where latency is actually spent."""
    lookback = lookback or config.WINDOW
    svcs = [service] if service else services()
    spans, _ = _collect(svcs, lookback, limit)
    child_time = defaultdict(int)
    for s in spans:
        child_time[(s["traceID"], s["parentSpanID"])] += s["duration_us"]
    rows = []
    for s in spans:
        if service and s["service"] != service:
            continue
        rows.append({"where": f"{s['service']} :: {s['operation']}",
                     "duration_ms": round(s["duration_us"] / 1000, 1),
                     "self_ms": round(max(0, s["duration_us"] - child_time[(s["traceID"], s["spanID"])]) / 1000, 1),
                     "trace_id": s["traceID"], "calls_to": _peer(s)})
    rows.sort(key=lambda r: -r["self_ms"])
    agg = defaultdict(lambda: {"n": 0, "max_self_ms": 0.0, "trace_ids": []})
    for r in rows:
        a = agg[r["where"]]
        a["n"] += 1
        a["max_self_ms"] = max(a["max_self_ms"], r["self_ms"])
        if len(a["trace_ids"]) < 2:
            a["trace_ids"].append(r["trace_id"])
        a["calls_to"] = r["calls_to"]
    out = sorted(({"where": k, **v} for k, v in agg.items()), key=lambda x: -x["max_self_ms"])[:top]
    return {"lookback": lookback, "slowest_by_self_time": out}


def get_trace(trace_id: str) -> dict:
    """One trace as a compact call tree: service, operation, duration, error message."""
    try:
        spans = _flatten_v3(_get(f"v3/traces/{trace_id}"))
    except requests.RequestException:
        spans = _flatten_v1(_get(f"traces/{trace_id}").get("data") or [])
    if not spans:
        return {"trace_id": trace_id, "error": "trace not found"}
    by_id = {s["spanID"]: s for s in spans}
    kids = defaultdict(list)
    for s in sorted(spans, key=lambda s: s["start"]):
        kids[s["parentSpanID"] if s["parentSpanID"] in by_id else "ROOT"].append(s)
    lines = []

    def walk(s, depth):
        if len(lines) >= 40:
            return
        flag = " ERROR" if _is_error(s) else ""
        m = f" \"{_msg(s)}\"" if _is_error(s) and _msg(s) else ""
        lines.append(f"{'  ' * depth}{s['service']} :: {s['operation']} {s['duration_us'] / 1000:.1f}ms{flag}{m}")
        for c in kids[s["spanID"]]:
            walk(c, depth + 1)

    for root in kids["ROOT"]:
        walk(root, 0)
    return {"trace_id": trace_id, "spans": len(spans), "tree": lines}


# backwards-compatible name used by older code
def analyse(lookback: str = None, per_service_limit: int = 30) -> dict:
    return error_origins(lookback, per_service_limit)
