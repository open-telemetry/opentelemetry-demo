"""Step 1 - DETECT: alert rules over the demo's metrics (+ container state), evaluated every POLL_SECONDS.

An alert fires when the same condition holds for ALERT_CONSECUTIVE polls in a row (avoids flapping):
  * server error rate >= ALERT_ERROR_RATE and >= baseline + ALERT_ERROR_DELTA
  * p95 latency >= ALERT_P95_FACTOR x baseline and >= ALERT_P95_MIN_MS
  * request rate dropped below 20% of baseline (service stopped / unreachable)
  * an app container is not running, restarting, or was OOM-killed
While everything is healthy the watcher refreshes the healthy runtime baseline (CPU / memory per container).
"""
import time
import uuid

from agent import config, topology
from agent.tools import deploys, metrics

IGNORE = {"load-generator", "jaeger", "prometheus", "grafana", "opensearch", "otel-collector"}


def evaluate(health: dict, runtime: dict = None) -> dict:
    reasons, services = [], set()
    for s, h in (health or {}).items():
        if s in IGNORE:
            continue
        if h["error_rate"] >= config.ALERT_ERROR_RATE and \
                h["error_rate"] >= h["error_rate_baseline"] + config.ALERT_ERROR_DELTA:
            reasons.append(f"{s} error rate {h['error_rate']:.1%} (baseline {h['error_rate_baseline']:.1%})")
            services.add(s)
        elif metrics.error_spans_up(h):
            reasons.append(f"{s} {h['error_spans_per_s']:.3f} error spans/s "
                           f"(baseline {h.get('error_spans_per_s_baseline', 0):.3f})")
            services.add(s)
        if h.get("baseline_source") != "none" and h["p95_ms_baseline"] > 0 and \
                h["p95_ms"] >= config.ALERT_P95_MIN_MS and \
                h["p95_ms"] >= config.ALERT_P95_FACTOR * h["p95_ms_baseline"]:
            reasons.append(f"{s} p95 {h['p95_ms']:.0f}ms (baseline {h['p95_ms_baseline']:.0f}ms)")
            services.add(s)
        if h["req_per_s_baseline"] > 0.2 and h["req_per_s"] < 0.2 * h["req_per_s_baseline"]:
            reasons.append(f"{s} traffic {h['req_per_s']:.2f} req/s (baseline {h['req_per_s_baseline']:.2f})")
            services.add(s)
    for name, c in ((runtime or {}).get("abnormal_containers") or {}).items():
        if name in IGNORE or name not in topology.APP_CONTAINERS:
            continue
        if c["status"] != "running":
            reasons.append(f"container {name} is {c['status']}")
            services.add(name)
        elif c.get("oom_killed") or (c.get("restart_count") and (c.get("started_min_ago") or 99) < 10):
            reasons.append(f"container {name} restarting/OOM (restarts {c['restart_count']})")
            services.add(name)
        elif c.get("health") == "unhealthy":
            reasons.append(f"container {name} unhealthy")
            services.add(name)
    return {"firing": bool(reasons), "reasons": reasons, "services": sorted(services)}


def snapshot(window: str = None) -> dict:
    """One poll. Tolerates a dead data source (an alert can still fire from the other)."""
    out = {"health": {}, "runtime": {}, "errors": []}
    try:
        out["health"] = metrics.service_health(window)
    except Exception as e:
        out["errors"].append(f"prometheus: {type(e).__name__}")
    try:
        out["runtime"] = deploys.analyse()
    except Exception as e:
        out["errors"].append(f"docker: {type(e).__name__}")
    out["eval"] = evaluate(out["health"], out["runtime"])
    return out


def new_alert(ev: dict, source: str = "watch") -> dict:
    return {"alert_id": f"alert-{uuid.uuid4().hex[:6]}", "source": source,
            "incident_id": f"inc-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}",
            "fired_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "reasons": ev["reasons"], "services": ev["services"]}


def watch(log=print, max_polls: int = None) -> dict:
    """Block until an alert fires; return it."""
    streak, healthy, polls = 0, 0, 0
    log(f"watching every {config.POLL_SECONDS}s (fires after {config.ALERT_CONSECUTIVE} bad polls) - Ctrl-C to stop")
    while max_polls is None or polls < max_polls:
        polls += 1
        snap = snapshot()
        ev = snap["eval"]
        if ev["firing"]:
            streak += 1
            healthy = 0
            log(f"  [{time.strftime('%H:%M:%S')}] suspicious ({streak}/{config.ALERT_CONSECUTIVE}): "
                + "; ".join(ev["reasons"][:3]))
            if streak >= config.ALERT_CONSECUTIVE:
                return new_alert(ev)
        else:
            streak = 0
            healthy += 1
            log(f"  [{time.strftime('%H:%M:%S')}] healthy" + (f" (could not read: {snap['errors']})" if snap["errors"] else ""))
            if healthy % 6 == 1 and not snap["errors"]:
                try:
                    deploys.save_baseline()
                    metrics.save_health_baseline()
                except Exception:
                    pass
        time.sleep(config.POLL_SECONDS)
    return None
