"""EYES / metrics: Prometheus queries.

Main source is the collector's span metrics (traces_span_metrics_*), which exist for EVERY
service regardless of language, labelled by service_name and status_code.
Each function returns small, pre-summarised dicts (not raw Prometheus JSON) so the LLM stays focused.
"""
import json
import time

import requests

from agent import config

HEALTH_BASELINE_FILE = config.RUNS / "metrics_baseline.json"


def save_health_baseline(window: str = None) -> dict:
    """Snapshot of per-service rate / error rate / p95 while the shop is HEALTHY.
    Used as the baseline instead of 'offset 30m' (which is empty right after start-up and polluted
    when the previous practice fault was <30 min ago)."""
    h = service_health(window, use_saved=False)
    snap = {s: {"req_per_s": v["req_per_s"], "error_rate": v["error_rate"], "p95_ms": v["p95_ms"],
                "error_spans_per_s": v["error_spans_per_s"]} for s, v in h.items()}
    HEALTH_BASELINE_FILE.write_text(json.dumps({"taken_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                                "services": snap}), encoding="utf-8")
    return snap


def _saved_baseline() -> dict:
    try:
        return json.loads(HEALTH_BASELINE_FILE.read_text(encoding="utf-8"))["services"]
    except Exception:
        return {}

CALLS = "traces_span_metrics_calls_total"
DUR = "traces_span_metrics_duration_milliseconds_bucket"


def _q(promql: str) -> list:
    r = requests.get(f"{config.PROMETHEUS_URL}/api/v1/query", params={"query": promql},
                     timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()["data"]["result"]


def _by_service(promql: str) -> dict:
    out = {}
    for row in _q(promql):
        svc = row["metric"].get("service_name", "?")
        try:
            v = float(row["value"][1])
        except (ValueError, KeyError):
            continue
        if v == v:  # drop NaN
            out[svc] = v
    return out


def list_metric_names(contains: str = "") -> list:
    """Discovery helper: what metrics actually exist? (use this, don't guess names)"""
    r = requests.get(f"{config.PROMETHEUS_URL}/api/v1/label/__name__/values", timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return [m for m in r.json()["data"] if contains in m]


def service_health(window: str = None, baseline_offset: str = None, use_saved: bool = True) -> dict:
    """Per-service request rate, error rate and p95 latency: NOW vs BASELINE.
    Baseline = saved healthy snapshot (python -m agent.main baseline) if present, else the same
    window BASELINE_OFFSET ago; 'baseline_source' says which (none = no history -> no latency rule)."""
    w = window or config.WINDOW
    off = baseline_offset or config.BASELINE_OFFSET
    server = 'span_kind="SPAN_KIND_SERVER"'
    err = 'status_code="STATUS_CODE_ERROR"'

    def block(offset=""):
        o = f" offset {offset}" if offset else ""
        rate = _by_service(f"sum by (service_name) (rate({CALLS}{{{server}}}[{w}]{o}))")
        errs = _by_service(f"sum by (service_name) (rate({CALLS}{{{server},{err}}}[{w}]{o}))")
        # client-side errors catch services whose *outgoing* calls fail (e.g. checkout -> payment)
        all_errs = _by_service(f"sum by (service_name) (rate({CALLS}{{{err}}}[{w}]{o}))")
        p95 = _by_service(
            f"histogram_quantile(0.95, sum by (service_name, le) (rate({DUR}{{{server}}}[{w}]{o})))")
        return rate, errs, all_errs, p95

    now = block()
    base = block(off)
    # include baseline-only services: a stopped service disappears from "now" -> traffic drop to 0
    services = set(now[0]) | set(now[2]) | set(now[3]) | set(base[0])
    result = {}
    for s in sorted(services):
        rate, base_rate = now[0].get(s, 0.0), base[0].get(s, 0.0)
        er = now[1].get(s, 0.0) / rate if rate else 0.0
        base_er = base[1].get(s, 0.0) / base_rate if base_rate else 0.0
        result[s] = {
            "req_per_s": round(rate, 3),
            "req_per_s_baseline": round(base_rate, 3),
            "error_rate": round(er, 4),
            "error_rate_baseline": round(base_er, 4),
            "error_spans_per_s": round(now[2].get(s, 0.0), 3),
            "error_spans_per_s_baseline": round(base[2].get(s, 0.0), 3),
            "p95_ms": round(now[3].get(s, 0.0), 1),
            "p95_ms_baseline": round(base[3].get(s, 0.0), 1),
            "baseline_source": "offset" if (s in base[0] or s in base[3]) else "none",
        }
    saved = _saved_baseline() if use_saved else {}
    for s, r in result.items():
        b = saved.get(s)
        if b:
            r["req_per_s_baseline"], r["error_rate_baseline"], r["p95_ms_baseline"] = \
                b["req_per_s"], b["error_rate"], b["p95_ms"]
            r["error_spans_per_s_baseline"] = b.get("error_spans_per_s", r["error_spans_per_s_baseline"])
            r["baseline_source"] = "saved"
    return result


def top_error_operations(window: str = None, k: int = 8) -> list:
    """Which span names (operations) are failing most -> points at the exact RPC/route."""
    w = window or config.WINDOW
    rows = _q(f'topk({k}, sum by (service_name, span_name) '
              f'(rate({CALLS}{{status_code="STATUS_CODE_ERROR"}}[{w}])))')
    out = []
    for r in rows:
        v = float(r["value"][1])
        if v > 0:
            out.append({"service": r["metric"].get("service_name"),
                        "operation": r["metric"].get("span_name"),
                        "errors_per_s": round(v, 3)})
    return out


def error_spans_up(h: dict) -> bool:
    b = h.get("error_spans_per_s_baseline", 0) or 0
    return h.get("error_spans_per_s", 0) >= 0.03 and h["error_spans_per_s"] >= 3 * b + 0.02


def anomalies(health: dict) -> list:
    """Turn the health table into a short list of human-readable anomaly facts."""
    facts = []
    for s, h in health.items():
        if h["error_rate"] >= 0.02 and h["error_rate"] > 2 * h["error_rate_baseline"] + 0.01:
            facts.append({"service": s, "type": "error_rate_up",
                          "detail": f"error rate {h['error_rate']:.1%} (baseline {h['error_rate_baseline']:.1%})",
                          "severity": min(1.0, h["error_rate"] * 2)})
        elif error_spans_up(h):
            # low-traffic services: the ratio is noisy, but error spans/s far above baseline is not
            facts.append({"service": s, "type": "error_rate_up",
                          "detail": f"{h['error_spans_per_s']:.3f} error spans/s "
                                    f"(baseline {h.get('error_spans_per_s_baseline', 0):.3f})",
                          "severity": min(1.0, 0.3 + 3 * h["error_spans_per_s"])})
        if h.get("baseline_source") != "none" and h["p95_ms_baseline"] > 0 and \
                h["p95_ms"] > 200 and h["p95_ms"] > 2.5 * h["p95_ms_baseline"]:
            facts.append({"service": s, "type": "latency_up",
                          "detail": f"p95 {h['p95_ms']:.0f}ms (baseline {h['p95_ms_baseline']:.0f}ms)",
                          "severity": min(1.0, h["p95_ms"] / (h["p95_ms_baseline"] * 10 + 1))})
        if h["req_per_s_baseline"] > 0.2 and h["req_per_s"] > 3 * h["req_per_s_baseline"]:
            facts.append({"service": s, "type": "traffic_spike",
                          "detail": f"{h['req_per_s']:.1f} req/s (baseline {h['req_per_s_baseline']:.1f})",
                          "severity": 0.6})
        if h["req_per_s_baseline"] > 0.2 and h["req_per_s"] < 0.2 * h["req_per_s_baseline"]:
            facts.append({"service": s, "type": "traffic_drop",
                          "detail": f"{h['req_per_s']:.2f} req/s (baseline {h['req_per_s_baseline']:.2f})",
                          "severity": 0.7})
    return sorted(facts, key=lambda f: -f["severity"])


def optional_signals() -> dict:
    """Extra signals that only exist for some services. Missing metrics are silently skipped.
    Run list_metric_names('kafka') / ('jvm') etc. once and add what you find here."""
    queries = {
        "kafka_consumer_lag": "sum by (group) (kafka_consumergroup_lag)",
        "jvm_gc_seconds_rate": "sum by (service_name) (rate(jvm_gc_duration_seconds_sum[5m]))",
    }
    out = {}
    for name, q in queries.items():
        try:
            rows = _q(q)
            if rows:
                out[name] = {next(iter(r["metric"].values()), "all"): round(float(r["value"][1]), 3) for r in rows}
        except Exception:
            pass
    return out


def service_detail(service: str, window: str = None) -> dict:
    """Drill into ONE service: per-operation rate / error rate / p95, now vs baseline,
    plus its outgoing (client) calls that fail -> tells you which dependency it is waiting on."""
    w = window or config.WINDOW
    off = config.BASELINE_OFFSET
    sel = f'service_name="{service}"'
    err = 'status_code="STATUS_CODE_ERROR"'

    def by_op(q):
        out = {}
        for row in _q(q):
            try:
                v = float(row["value"][1])
            except (ValueError, KeyError):
                continue
            if v == v:
                out[row["metric"].get("span_name", "?")] = v
        return out

    rate = by_op(f"sum by (span_name) (rate({CALLS}{{{sel}}}[{w}]))")
    errs = by_op(f"sum by (span_name) (rate({CALLS}{{{sel},{err}}}[{w}]))")
    base_errs = by_op(f"sum by (span_name) (rate({CALLS}{{{sel},{err}}}[{w}] offset {off}))")
    p95 = by_op(f"histogram_quantile(0.95, sum by (span_name, le) (rate({DUR}{{{sel}}}[{w}])))")
    p95b = by_op(f"histogram_quantile(0.95, sum by (span_name, le) (rate({DUR}{{{sel}}}[{w}] offset {off})))")
    ops = []
    for op in set(rate) | set(errs):
        r = rate.get(op, 0.0)
        ops.append({"operation": op, "req_per_s": round(r, 3),
                    "error_rate": round(errs.get(op, 0.0) / r, 4) if r else 0.0,
                    "errors_per_s_baseline": round(base_errs.get(op, 0.0), 4),
                    "p95_ms": round(p95.get(op, 0.0), 1), "p95_ms_baseline": round(p95b.get(op, 0.0), 1)})
    ops.sort(key=lambda o: (-o["error_rate"], -o["p95_ms"]))
    return {"service": service, "window": w, "baseline_offset": off, "operations": ops[:12]}


def query(promql: str) -> dict:
    """Read-only PromQL for anything the other tools do not cover. Output is truncated."""
    if any(bad in promql for bad in ("delete", "admin")):
        raise ValueError("only read queries are allowed")
    rows = _q(promql)
    return {"promql": promql, "series": len(rows),
            "result": [{"labels": r["metric"], "value": r.get("value", [None, None])[1]} for r in rows[:20]]}
