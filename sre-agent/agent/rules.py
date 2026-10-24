"""BRAIN part 1: deterministic, telemetry-only scoring of candidate root causes.

Used three ways: (1) as a tool/hint for the LLM, (2) as the fallback diagnosis when the LLM fails,
(3) as a cross-check of the LLM ("reviewer"): disagreement lowers confidence.

It does NOT read feature-flag settings and contains no per-incident answers. It reasons from
signals: where errors originate in traces, which dependency a failing call targets, error logs,
latency self-time, metrics vs baseline, and container state.
"""
from collections import defaultdict

from agent import topology

FAULT_TYPES = ["application_error", "service_down", "crash_loop", "dependency_unavailable", "latency",
               "network_fault", "high_cpu", "memory_leak", "gc_pressure", "cache_failure", "queue_backlog",
               "traffic_flood", "readiness_failure", "db_contention", "resource_starvation", "unknown"]

# gRPC service / db system / peer name -> container name (to blame the CALLEE of a failing call)
PEER_TO_SVC = {
    "oteldemo.PaymentService": "payment", "oteldemo.CartService": "cart",
    "oteldemo.CheckoutService": "checkout", "oteldemo.CurrencyService": "currency",
    "oteldemo.ProductCatalogService": "product-catalog", "oteldemo.RecommendationService": "recommendation",
    "oteldemo.ShippingService": "shipping", "oteldemo.AdService": "ad", "oteldemo.EmailService": "email",
    "oteldemo.QuoteService": "quote", "flagd.evaluation.v1.Service": "flagd",
    "flagd.evaluation.v2.Service": "flagd",
    "redis": "valkey-cart", "valkey": "valkey-cart", "valkey-cart": "valkey-cart",
    "postgresql": "astronomy-db", "postgres": "astronomy-db", "astronomy-db": "astronomy-db",
    "kafka": "kafka", "orders": "kafka",
}
UNREACHABLE = ("unavailable", "connection refused", "no such host", "connect: ", "dns", "unreachable",
               "deadline", "timeout", "timed out", "econnrefused", "broken pipe", "reset by peer",
               "not possible to connect", "unable to connect", "unabletoconnect", "could not connect",
               "failed to connect", "connection error", "no connection", "connection closed")
# services that are part of the shop's tooling, never the "victim app"
TOOLING = {"load-generator", "otel-collector", "otelcol-contrib", "otelcol", "jaeger", "prometheus", "grafana",
           "opensearch", "frontend-proxy", "flagd-ui", "opamp-server", "telemetry-docs"}


def _svc(where: str) -> str:
    return where.split(" :: ")[0]


def _peer_svc(peer: str):
    if not peer:
        return None
    for k, v in PEER_TO_SVC.items():
        if k.lower() in peer.lower():
            return v
    p = peer.split(":")[0]
    return p if p in topology.DEPS or p in topology.INFRA else None


def build_bundle(session) -> dict:
    """The six broad tools; cheap enough to always run (cached in the session)."""
    return {"health": session.call("get_service_health"),
            "failing_ops": session.call("get_failing_operations"),
            "origins": session.call("get_error_origins"),
            "slow": session.call("get_slow_operations"),
            "logs": session.call("get_error_log_summary"),
            "runtime": session.call("get_runtime_events")}


def _ok(x, key, default):
    return x.get(key, default) if isinstance(x, dict) and "error" not in x else default


def is_quiet(b: dict) -> bool:
    """True when nothing looks wrong (no alertable anomaly, few error origins, no runtime events)."""
    anomalies = _ok(b["health"], "anomalies", [])
    origins = [o for o in _ok(b["origins"], "error_origins", []) if _svc(o["where"]) not in TOOLING]
    events = _ok(b["runtime"], "events", [])
    real_events = [e for e in events if "(re)started" not in e and e.split(" ")[0] not in TOOLING]
    return not anomalies and sum(o["count"] for o in origins) < 3 and not real_events


def rank(b: dict) -> list:
    score = defaultdict(float)
    sources = defaultdict(set)
    signals = defaultdict(list)
    votes = defaultdict(lambda: defaultdict(float))
    component = {}

    def add(s, pts, src, sig, ft=None, w=1.0, comp=None):
        if not s:
            return
        score[s] += pts
        sources[s].add(src)
        signals[s].append({"source": src, "signal": sig})
        if ft:
            votes[s][ft] += w
        if comp and s not in component:
            component[s] = comp

    anomalies = _ok(b["health"], "anomalies", [])
    health = _ok(b["health"], "services", {})
    anomalous = {a["service"] for a in anomalies}

    # --- TRACES: error origins (strongest signal) ---
    origins = _ok(b["origins"], "error_origins", [])
    total = sum(o["count"] for o in origins) or 1
    for o in origins:
        s, op = _svc(o["where"]), o["where"].split(" :: ", 1)[-1]
        msg = " ".join(o.get("top_messages", [])).lower()
        ids = ",".join(o.get("example_trace_ids", [])[:2])
        sig = f"trace error origin {o['where']} ({o['count']} spans) msg={o.get('top_messages', [''])[:1]} traces={ids}"
        callee = next((_peer_svc(p) for p in o.get("calls_to", []) if _peer_svc(p)), None)
        if callee and callee != s and any(k in msg for k in UNREACHABLE):
            # caller's outgoing call fails because the callee is not reachable -> blame callee
            ft = "dependency_unavailable" if callee in topology.INFRA else "service_down"
            add(callee, 4 * o["count"] / total + 0.5, "traces", f"{sig} -> {s} cannot reach {callee}", ft, 2,
                comp=f"{s} -> {callee}")
            add(s, 0.3, "traces", sig)
        elif "cache" in msg or "redis" in msg or "valkey" in msg:
            add(s, 4 * o["count"] / total, "traces", sig, "cache_failure", 1.5, comp=op)
        elif any(k in msg for k in ("lock", "deadlock", "too many connections")):
            add(s, 4 * o["count"] / total, "traces", sig, "db_contention", 1.5, comp=op)
        else:
            add(s, 4 * o["count"] / total, "traces", sig, "application_error", 1, comp=op)

    # --- TRACES: latency self-time, only when a latency anomaly exists ---
    lat_services = {a["service"] for a in anomalies if a["type"] == "latency_up"}
    if lat_services:
        scope = set().union(*[topology.descendants(s) | {s} for s in lat_services])
        slow = [x for x in _ok(b["slow"], "slowest_by_self_time", [])
                if _svc(x["where"]) in scope and x["max_self_ms"] > 300]
        for x in slow[:3]:
            s = _svc(x["where"])
            callee = _peer_svc(x.get("calls_to", ""))
            sig = (f"latency self-time {x['where']} max {x['max_self_ms']}ms over {x['n']} spans "
                   f"traces={','.join(x['trace_ids'])}")
            if callee and callee != s:
                # time is spent waiting on the wire / in the callee
                add(callee, 1.5, "traces", sig + f" (waiting on {callee})", "latency", 1,
                    comp=f"{s} -> {callee}")
                votes[callee]["network_fault"] += 0.6
            else:
                add(s, 1.5, "traces", sig, "latency", 1, comp=x["where"].split(" :: ", 1)[-1])

    # --- METRICS ---
    ft_of = {"error_rate_up": "application_error", "latency_up": "latency",
             "traffic_spike": "traffic_flood", "traffic_drop": "service_down"}
    edge_spikes = [a for a in anomalies if a["type"] == "traffic_spike" and a["service"] in ("frontend", "frontend-proxy")]
    for a in anomalies:
        w = 1.5 * a["severity"]
        if a in edge_spikes:
            # a flood enters at the edge; frontend-proxy is a pass-through, so credit the frontend app
            add("frontend", w + 1.0, "metrics", f"{a['service']} {a['type']}: {a['detail']}", "traffic_flood", 2,
                comp="incoming traffic (homepage load)")
            continue
        add(a["service"], w, "metrics", f"{a['type']}: {a['detail']}", ft_of[a["type"]], 0.7)
    fo = b.get("failing_ops")
    for op in (fo if isinstance(fo, list) else [])[:5]:
        if op["service"] in TOOLING or op["errors_per_s"] < 0.01:
            continue
        # a failing operation in span metrics is independent of the trace sample -> counts as "metrics"
        add(op["service"], 0.3, "metrics", f"failing op {op['operation']} {op['errors_per_s']}/s")

    # --- LOGS ---
    by_svc = _ok(b["logs"], "error_logs_by_service", {})
    tot = sum(v["error_lines"] for v in by_svc.values()) or 1
    for s, v in by_svc.items():
        if s in TOOLING:
            continue
        txt = " ".join(v["top_messages"]).lower()
        ft = None
        for kw, f in (("out of memory", "memory_leak"), ("outofmemory", "memory_leak"), ("heap", "memory_leak"),
                      ("gc overhead", "gc_pressure"), ("garbage", "gc_pressure"), ("cache", "cache_failure"),
                      ("lock", "db_contention"), ("readiness", "readiness_failure"),
                      ("connection refused", "dependency_unavailable"), ("lag", "queue_backlog")):
            if kw in txt:
                ft = f
                break
        add(s, 1.5 * v["error_lines"] / tot, "logs",
            f"{v['error_lines']} error log lines, top: {v['top_messages'][0][:120]}", ft or "application_error",
            0.7 if ft else 0.3)
        # log says it cannot reach X -> X is suspect
        for peer, svc in PEER_TO_SVC.items():
            if svc != s and peer.lower() in txt and any(k in txt for k in UNREACHABLE):
                add(svc, 1.0, "logs", f"{s} logs fail to reach {svc}: {v['top_messages'][0][:100]}",
                    "dependency_unavailable" if svc in topology.INFRA else "service_down", 1.2)
                break

    # --- RUNTIME (docker) ---
    for e in _ok(b["runtime"], "events", []):
        s = e.split(" ")[0]
        if s in TOOLING:
            continue
        if "(re)started" in e:
            add(s, 0.2, "runtime", e)
        elif " is exited" in e or " is dead" in e or " is paused" in e or " is created" in e:
            add(s, 3.0, "runtime", e, "dependency_unavailable" if s in topology.INFRA else "service_down", 3)
        elif "restarted" in e:
            add(s, 2.0, "runtime", e, "crash_loop", 2)
        elif "OOM" in e:
            add(s, 2.5, "runtime", e, "memory_leak", 3)
        elif "memory" in e:
            add(s, 1.5, "runtime", e, "memory_leak", 2)
        elif "CPU" in e:
            add(s, 1.5, "runtime", e, "high_cpu", 2)
        elif "unhealthy" in e:
            add(s, 1.5, "runtime", e, "readiness_failure", 1.5)

    # --- DEPENDENCY WALK: upstream services of a failing dependency are victims ---
    direct = {s for s in score if sources[s] & {"traces", "logs", "runtime"} and score[s] > 0.8}
    for s in list(score):
        if any(d in direct for d in topology.descendants(s)):
            score[s] *= 0.4
            signals[s].append({"source": "note", "signal": "discounted: a downstream dependency fails on its own"})
    for s in list(score):
        if s in TOOLING and s not in ("frontend-proxy",):
            score[s] *= 0.3

    ranked = []
    for s, sc in sorted(score.items(), key=lambda kv: -kv[1])[:5]:
        v = votes[s]
        ft = max(v, key=v.get) if v else "unknown"
        n_src = len(sources[s])
        conf = min(0.95, 0.2 + 0.2 * n_src + (0.1 if s in anomalous else 0))
        if ft == "traffic_flood" and len(edge_spikes) >= 2:
            conf = min(0.95, conf + 0.3)   # two independent edge measurements agree
        ranked.append({"service": s, "score": round(sc, 2), "fault_type_guess": ft,
                       "component": component.get(s), "evidence_sources": sorted(sources[s]),
                       "evidence_confidence": round(conf, 2), "signals": signals[s][:6]})
    if len(ranked) > 1 and ranked[0]["score"] < 1.3 * ranked[1]["score"]:
        ranked[0]["evidence_confidence"] = round(ranked[0]["evidence_confidence"] * 0.75, 2)
        ranked[0]["note"] = f"close runner-up: {ranked[1]['service']}"
    if ranked and ranked[0]["score"] < 1.0:
        ranked[0]["evidence_confidence"] = round(min(ranked[0]["evidence_confidence"], 0.4), 2)
    return ranked
