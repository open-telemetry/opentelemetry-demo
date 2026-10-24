"""Raw telemetry check for ONE service - independent of the agent's parsing code.

Answers "is this fault actually visible in logs / metrics / traces / docker?" before you trust the agent.

  python scripts/fault_check.py payment              # last 5 min
  python scripts/fault_check.py payment --minutes 10
  python scripts/fault_check.py all                  # quick table for every service

Run it once while HEALTHY and once 2-3 min AFTER injecting the fault, and compare.
Reads URLs from .env (PROMETHEUS_URL, JAEGER_URL, OPENSEARCH_URL) like the agent does.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

PROM = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
JAEGER = os.getenv("JAEGER_URL", "http://localhost:8080/jaeger/ui")
OS_URL = os.getenv("OPENSEARCH_URL", "")
ERR = re.compile(r"error|exception|fail|refused|unavailable|timeout|oom|panic|fatal", re.I)
CALLS = "traces_span_metrics_calls_total"
DUR = "traces_span_metrics_duration_milliseconds_bucket"


def h(t):
    print(f"\n=== {t} " + "=" * max(0, 70 - len(t)))


def sh(args, timeout=15):
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except Exception as e:
        return 1, str(e)


def prom(q):
    r = requests.get(f"{PROM}/api/v1/query", params={"query": q}, timeout=8)
    r.raise_for_status()
    return r.json()["data"]["result"]


def val(rows):
    try:
        return round(float(rows[0]["value"][1]), 4) if rows else 0.0
    except (ValueError, KeyError):
        return None


def check_docker(svc, minutes):
    h(f"DOCKER  {svc}")
    code, out = sh(["docker", "inspect", svc, "--format",
                    "status={{.State.Status}} restarts={{.RestartCount}} oom={{.State.OOMKilled}} "
                    "exit={{.State.ExitCode}} started={{.State.StartedAt}} health={{if .State.Health}}{{.State.Health.Status}}{{end}}"])
    print(("  " + out.strip()) if code == 0 else f"  !! no container '{svc}' ({out.strip()[:100]})")
    code, out = sh(["docker", "stats", "--no-stream", "--format", "cpu={{.CPUPerc}} mem={{.MemPerc}} ({{.MemUsage}})", svc], 30)
    if code == 0:
        print("  " + out.strip())
    code, out = sh(["docker", "logs", "--since", f"{minutes}m", "--timestamps", svc], 15)
    lines = out.splitlines() if code == 0 else []
    errs = [l for l in lines if ERR.search(l)]
    print(f"  docker logs last {minutes}m: {len(lines)} lines, {len(errs)} error-looking")
    for l in errs[-5:]:
        print("    | " + l[:200])
    return len(errs)


def os_url():
    if OS_URL:
        return OS_URL
    code, out = sh(["docker", "port", "opensearch", "9200"], 5)
    return "http://" + out.strip().splitlines()[0].replace("0.0.0.0", "localhost") if code == 0 and out.strip() else ""


def check_opensearch(svc, minutes):
    h(f"OPENSEARCH (otel-logs-*)  {svc}")
    url = os_url()
    if not url:
        print("  !! opensearch not reachable (container down or port not published)")
        return None
    try:
        idx = requests.get(f"{url}/_cat/indices/otel-logs-*?h=index,docs.count", timeout=5).text.strip()
        print("  indices: " + (idx.replace("\n", " | ") or "NONE - logs are not being exported"))
        body = {"size": 5, "sort": [{"@timestamp": {"order": "desc", "unmapped_type": "date"}}],
                "query": {"bool": {"must": [{"query_string": {"query": f'"{svc}"'}},
                                            {"range": {"@timestamp": {"gte": f"now-{minutes}m"}}}]}}}
        r = requests.post(f"{url}/otel-logs-*/_search", json=body, timeout=8).json()
        total = r["hits"]["total"]["value"] if isinstance(r["hits"]["total"], dict) else r["hits"]["total"]
        print(f"  docs mentioning '{svc}' in last {minutes}m: {total}")
        body["size"] = 300
        r2 = requests.post(f"{url}/otel-logs-*/_search", json=body, timeout=8).json()
        docs = [h["_source"] for h in r2.get("hits", {}).get("hits", [])]
        errs = [d for d in docs if ERR.search(json.dumps(d))]
        etotal = len(errs)
        print(f"  of the latest {len(docs)}, error-looking: {etotal}")
        if errs:
            d = errs[0]
            print("  example doc fields: " + ", ".join(sorted(d.keys()))[:300])
            print("  example: " + json.dumps(d)[:400])
        return etotal
    except Exception as e:
        print(f"  !! query failed: {type(e).__name__}: {str(e)[:150]}")
        return None


def check_prometheus(svc, minutes):
    h(f"PROMETHEUS (span metrics)  {svc}")
    w = f"{minutes}m"
    s = f'service_name="{svc}"'
    try:
        rate = val(prom(f'sum(rate({CALLS}{{{s},span_kind="SPAN_KIND_SERVER"}}[{w}]))'))
        rate_b = val(prom(f'sum(rate({CALLS}{{{s},span_kind="SPAN_KIND_SERVER"}}[{w}] offset 30m))'))
        err = val(prom(f'sum(rate({CALLS}{{{s},status_code="STATUS_CODE_ERROR"}}[{w}]))'))
        err_b = val(prom(f'sum(rate({CALLS}{{{s},status_code="STATUS_CODE_ERROR"}}[{w}] offset 30m))'))
        p95 = val(prom(f'histogram_quantile(0.95, sum by (le) (rate({DUR}{{{s}}}[{w}])))'))
        p95_b = val(prom(f'histogram_quantile(0.95, sum by (le) (rate({DUR}{{{s}}}[{w}] offset 30m)))'))
        print(f"  server req/s : now {rate}   30m ago {rate_b}")
        print(f"  error spans/s: now {err}   30m ago {err_b}")
        print(f"  p95 ms       : now {p95}   30m ago {p95_b}")
        ops = prom(f'topk(5, sum by (span_name) (rate({CALLS}{{{s},status_code="STATUS_CODE_ERROR"}}[{w}])))')
        for o in ops:
            if float(o["value"][1]) > 0:
                print(f"    failing op: {o['metric'].get('span_name')}  {float(o['value'][1]):.3f}/s")
        if rate == 0 and rate_b == 0:
            print("  !! no span metrics for this service name at all (wrong name? not instrumented?)")
        return err
    except Exception as e:
        print(f"  !! query failed: {type(e).__name__}: {str(e)[:150]}")
        return None


def _attrs(items):
    out = {}
    for i in items or []:
        v = i.get("value", {})
        out[i.get("key")] = next(iter(v.values()), None) if isinstance(v, dict) and v else v
    return out


def check_jaeger(svc, minutes):
    h(f"JAEGER (traces, v3 API)  {svc}")
    from datetime import datetime, timedelta, timezone
    end = datetime.now(timezone.utc)
    fmt = lambda d: d.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    try:
        r = requests.get(f"{JAEGER}/api/v3/traces", timeout=15, params={
            "query.serviceName": svc, "query.startTimeMin": fmt(end - timedelta(minutes=minutes)),
            "query.startTimeMax": fmt(end), "query.searchDepth": "50"})
        if r.status_code == 404 and "not found" in r.text.lower() and "trace" in r.text.lower():
            print(f"  no traces for {svc} in last {minutes}m")
            return 0
        r.raise_for_status()
        res = r.json().get("result", r.json())
        traces, err_traces, msgs = set(), set(), {}
        for rg in res.get("resourceSpans", []):
            rsvc = _attrs(rg.get("resource", {}).get("attributes")).get("service.name")
            for sg in rg.get("scopeSpans", []):
                for sp in sg.get("spans", []):
                    traces.add(sp.get("traceId"))
                    st = sp.get("status", {}) or {}
                    if st.get("code") in (2, "STATUS_CODE_ERROR"):
                        err_traces.add(sp.get("traceId"))
                        if rsvc == svc:
                            a = _attrs(sp.get("attributes"))
                            m = str(a.get("exception.message") or st.get("message") or sp.get("name"))[:120]
                            msgs[m] = msgs.get(m, 0) + 1
        print(f"  traces involving {svc} in last {minutes}m: {len(traces)}  (with an error: {len(err_traces)})")
        for m, c in sorted(msgs.items(), key=lambda kv: -kv[1])[:4]:
            print(f"    {c}x error span in {svc}: {m}")
        if err_traces:
            ex = next(iter(err_traces))
            print(f"  example error trace: {ex}  -> open {JAEGER}/trace/{ex}")
        return len(err_traces)
    except Exception as e:
        print(f"  !! query failed: {type(e).__name__}: {str(e)[:150]}  (check JAEGER_URL={JAEGER})")
        return None


def all_table(minutes):
    w = f"{minutes}m"
    try:
        rows = prom(f'sum by (service_name) (rate({CALLS}{{span_kind="SPAN_KIND_SERVER"}}[{w}]))')
        errs = {r["metric"]["service_name"]: float(r["value"][1]) for r in
                prom(f'sum by (service_name) (rate({CALLS}{{status_code="STATUS_CODE_ERROR"}}[{w}]))')}
    except Exception as e:
        print(f"prometheus unreachable: {e}")
        rows, errs = [], {}
    code, out = sh(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"])
    status = dict(l.split("\t", 1) for l in out.splitlines() if "\t" in l) if code == 0 else {}
    print(f"{'service':22} {'req/s':>8} {'err/s':>8}  container")
    names = sorted({r["metric"]["service_name"] for r in rows} | set(errs) | set(status))
    rates = {r["metric"]["service_name"]: float(r["value"][1]) for r in rows}
    for n in names:
        print(f"{n:22} {rates.get(n, 0):8.3f} {errs.get(n, 0):8.3f}  {status.get(n, '-')}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("service")
    p.add_argument("--minutes", type=int, default=5)
    a = p.parse_args()
    print(f"fault_check {a.service}  ({time.strftime('%H:%M:%S')}, last {a.minutes} min)")
    if a.service == "all":
        all_table(a.minutes)
        return
    res = {"docker_log_errors": check_docker(a.service, a.minutes),
           "opensearch_errors": check_opensearch(a.service, a.minutes),
           "prometheus_error_spans_per_s": check_prometheus(a.service, a.minutes),
           "jaeger_error_traces": check_jaeger(a.service, a.minutes)}
    h("SUMMARY")
    for k, v in res.items():
        flag = "not readable" if v is None else ("SIGNAL" if v else "nothing")
        print(f"  {k:30} {v!s:>8}   {flag}")


if __name__ == "__main__":
    sys.exit(main())
