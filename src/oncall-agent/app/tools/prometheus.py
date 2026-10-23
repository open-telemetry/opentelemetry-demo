import time
from typing import Any

import httpx

from app.config import HOST_FALLBACK_URLS, PROMETHEUS_URL


def _query_prom(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    urls = [PROMETHEUS_URL, HOST_FALLBACK_URLS.get("prometheus", "http://localhost:9090")]
    last_err: Exception | None = None
    for url in urls:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{url}/api/v1/{endpoint}", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Prometheus unreachable at {urls}: {last_err}")


def get_health_overview(lookback_min: int = 15) -> str:
    window = f"{max(2, lookback_min // 5)}m"
    calls_query = f"sum by (service_name) (rate(traces_span_metrics_calls_total[{window}]))"
    errors_query = (
        f'sum by (service_name) (rate(traces_span_metrics_calls_total{{status_code="STATUS_CODE_ERROR"}}[{window}]))'
    )
    p95_query = f"histogram_quantile(0.95, sum by (service_name, le) (rate(traces_span_metrics_duration_milliseconds_bucket[{window}])))"
    baseline_p95_query = (
        "histogram_quantile(0.95, sum by (service_name, le) (rate(traces_span_metrics_duration_milliseconds_bucket[30m])))"
    )

    try:
        calls_res = _query_prom("query", {"query": calls_query}).get("data", {}).get("result", [])
        errors_res = _query_prom("query", {"query": errors_query}).get("data", {}).get("result", [])
        p95_res = _query_prom("query", {"query": p95_query}).get("data", {}).get("result", [])
        base_res = _query_prom("query", {"query": baseline_p95_query}).get("data", {}).get("result", [])
    except Exception as e:
        return f"Error querying Prometheus health metrics: {e}"

    rps_map: dict[str, float] = {}
    for r in calls_res:
        svc = r.get("metric", {}).get("service_name")
        if svc:
            try:
                rps_map[svc] = float(r.get("value", [0, 0])[1])
            except (ValueError, IndexError):
                pass

    err_map: dict[str, float] = {}
    for r in errors_res:
        svc = r.get("metric", {}).get("service_name")
        if svc:
            try:
                err_map[svc] = float(r.get("value", [0, 0])[1])
            except (ValueError, IndexError):
                pass

    p95_map: dict[str, float] = {}
    for r in p95_res:
        svc = r.get("metric", {}).get("service_name")
        if svc:
            try:
                val = float(r.get("value", [0, 0])[1])
                p95_map[svc] = val if val == val else 0.0
            except (ValueError, IndexError):
                pass

    base_map: dict[str, float] = {}
    for r in base_res:
        svc = r.get("metric", {}).get("service_name")
        if svc:
            try:
                val = float(r.get("value", [0, 0])[1])
                base_map[svc] = val if val == val else 0.0
            except (ValueError, IndexError):
                pass

    services = sorted(set(rps_map.keys()) | set(err_map.keys()) | set(p95_map.keys()))
    if not services:
        return "No services found in span metrics."

    rows: list[dict[str, Any]] = []
    for svc in services:
        rps = rps_map.get(svc, 0.0)
        err_rps = err_map.get(svc, 0.0)
        err_pct = (err_rps / rps * 100.0) if rps > 0 else 0.0
        p95 = p95_map.get(svc, 0.0)
        base = base_map.get(svc, p95)
        ratio = (p95 / base) if base > 0 else 1.0

        anomaly_score = 0.0
        anomaly_tag = "OK"
        if err_pct >= 50.0:
            anomaly_score += 10.0
            anomaly_tag = "CRITICAL"
        elif err_pct >= 5.0:
            anomaly_score += 5.0
            anomaly_tag = "HIGH"
        elif err_pct > 0.0:
            anomaly_score += 1.0
            anomaly_tag = "WARN"

        if ratio >= 2.0 and p95 > 500:
            anomaly_score += 4.0
            if anomaly_tag in ("OK", "WARN"):
                anomaly_tag = "DEGRADED"

        rows.append({
            "service": svc,
            "rps": rps,
            "err_pct": err_pct,
            "p95": p95,
            "base": base,
            "tag": anomaly_tag,
            "score": anomaly_score,
        })

    rows.sort(key=lambda x: (x["score"], x["err_pct"], x["rps"]), reverse=True)

    lines = [
        "| Service | Req/s | Error % | p95 (ms) | Baseline (ms) | Status |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['service']} | {r['rps']:.2f} | {r['err_pct']:.1f}% | {r['p95']:.1f} | {r['base']:.1f} | {r['tag']} |"
        )

    out = "\n".join(lines)
    return out[:2000]


def query_prometheus(promql: str, lookback_min: int = 15) -> str:
    if not promql or not isinstance(promql, str):
        return "Error: promql query must be a non-empty string."

    now = int(time.time())
    start = now - (lookback_min * 60)
    step = max(15, (lookback_min * 60) // 20)

    try:
        data = _query_prom("query_range", {"query": promql, "start": start, "end": now, "step": step})
    except Exception as e:
        return f"Error executing PromQL query: {e}"

    results = data.get("data", {}).get("result", [])
    if not results:
        return f"No data returned for PromQL query: '{promql}'."

    lines = [f"PromQL: {promql} (lookback {lookback_min}m, step {step}s)", ""]
    for idx, item in enumerate(results[:10]):
        metric_labels = item.get("metric", {})
        label_str = ", ".join(f'{k}="{v}"' for k, v in sorted(metric_labels.items()))
        values = item.get("values", [])
        if not values:
            lines.append(f"[{idx+1}] {{{label_str}}}: no points")
            continue

        raw_floats: list[float] = []
        for ts, v in values:
            try:
                fl = float(v)
                if fl == fl:
                    raw_floats.append(fl)
            except (ValueError, TypeError):
                pass

        if not raw_floats:
            lines.append(f"[{idx+1}] {{{label_str}}}: no valid numeric points")
            continue

        min_val = min(raw_floats)
        max_val = max(raw_floats)
        last_val = raw_floats[-1]
        first_val = raw_floats[0]

        trend = "flat"
        if last_val > first_val * 1.15:
            trend = "rising"
        elif last_val < first_val * 0.85:
            trend = "falling"

        lines.append(
            f"[{idx+1}] {{{label_str}}}: last={last_val:.2f}, min={min_val:.2f}, max={max_val:.2f}, trend={trend} (points={len(raw_floats)})"
        )

    if len(results) > 10:
        lines.append(f"... truncated ({len(results) - 10} more series)")

    out = "\n".join(lines)
    return out[:2000]
