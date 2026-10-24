"""EYES / logs: OpenSearch (otel-logs-*) with a `docker logs` fallback (read-only).

Field names depend on the exporter mapping, so documents are parsed defensively.
Two views:
  * error_summary()  - error templates per service (numbers/ids collapsed so identical errors group)
  * search_logs()    - exact recent error lines for ONE service, quotable as evidence
"""
import re
import subprocess
from collections import Counter, defaultdict

import requests

from agent import config

ERR_RE = re.compile(
    r"\b(error|exception|fatal|panic|fail(ed|ure|s)?|timeout|timed out|refused|unavailable|oom|"
    r"out of memory|traceback|deadline exceeded|unreachable)\b|HTTP/\d(?:\.\d)?\"\s+5\d\d\b", re.I)
# observability tooling noise that is not an application incident
IGNORE_RE = re.compile(r"/grafana/|/jaeger/|/loadgen/|/feature/|upgrade_failed|otel-collector.*exporter", re.I)
NOISE_RE = re.compile(r"\b[0-9a-f]{16,}\b|\b[0-9a-f-]{36}\b|\d+", re.I)
SEV_ERR = ("ERROR", "FATAL", "CRITICAL", "SEVERE", "PANIC")


def _opensearch_url() -> str:
    if config.OPENSEARCH_URL:
        return config.OPENSEARCH_URL
    try:
        out = subprocess.run(["docker", "port", "opensearch", "9200"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        return "http://" + out.stdout.strip().splitlines()[0].replace("0.0.0.0", "localhost")
    except Exception:
        return ""


def _find(doc, keys):
    if isinstance(doc, dict):
        for k, v in doc.items():
            if k in keys and isinstance(v, (str, int)):
                return v
        for v in doc.values():
            r = _find(v, keys)
            if r is not None:
                return r
    return None


def _template(msg: str) -> str:
    return NOISE_RE.sub("#", msg)[:160]


def _is_err(sev: str, body: str) -> bool:
    if IGNORE_RE.search(body):
        return False
    return sev.upper() in SEV_ERR or bool(ERR_RE.search(body))


def _opensearch_docs(minutes: int, size: int = 1500) -> list:
    url = _opensearch_url()
    if not url:
        raise RuntimeError("opensearch not reachable")
    body = {"size": size, "sort": [{"@timestamp": {"order": "desc", "unmapped_type": "date"}}],
            "query": {"range": {"@timestamp": {"gte": f"now-{minutes}m"}}}}
    r = requests.post(f"{url}/{config.OPENSEARCH_INDEX}/_search", json=body, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    rows = []
    for h in r.json()["hits"]["hits"]:
        d = h["_source"]
        rows.append({"service": str(_find(d, {"service.name", "service_name", "serviceName"}) or "?"),
                     "severity": str(_find(d, {"severity.text", "severityText", "severity_text", "level"}) or ""),
                     "time": str(_find(d, {"@timestamp", "time", "observedTimestamp"}) or ""),
                     "body": str(_find(d, {"body", "message", "msg"}) or "")[:400],
                     "trace_id": str(_find(d, {"traceId", "trace_id", "traceID"}) or "")})
    return rows


def _docker_lines(container: str, minutes: int) -> list:
    try:
        out = subprocess.run(["docker", "logs", "--timestamps", "--since", f"{minutes}m", container],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12)
    except Exception:
        return []
    if out.returncode != 0:
        return []
    rows = []
    for line in (out.stdout + out.stderr).splitlines()[-3000:]:
        ts, _, body = line.partition(" ")
        rows.append({"service": container, "severity": "", "time": ts[:23], "body": body[:400], "trace_id": ""})
    return rows


def _rows(minutes: int, containers: list) -> tuple:
    try:
        rows = _opensearch_docs(minutes)
        if rows:
            return rows, "opensearch"
        note = "opensearch returned no docs"
    except Exception as e:
        note = f"opensearch unavailable ({str(e)[:60]})"
    rows = [r for c in containers for r in _docker_lines(c, minutes)]
    return rows, f"docker-logs ({note})"


def error_summary(containers: list, minutes: int = 5) -> dict:
    rows, source = _rows(minutes, containers)
    per, totals = defaultdict(Counter), Counter()
    for r in rows:
        totals[r["service"]] += 1
        if _is_err(r["severity"], r["body"]):
            per[r["service"]][f"[{r['severity'] or '?'}] {_template(r['body'])}"] += 1
    ranked = sorted(per.items(), key=lambda kv: -sum(kv[1].values()))
    return {"source": source, "log_lines_scanned": len(rows), "minutes": minutes,
            "error_logs_by_service": {s: {"error_lines": sum(c.values()), "total_lines": totals[s],
                                          "top_messages": [f"{n}x {m}" for m, n in c.most_common(3)]}
                                      for s, c in ranked[:8]},
            "services_with_no_logs": sorted(set(containers) - set(totals))[:20]}


def search_logs(service: str, minutes: int = 5, contains: str = "", limit: int = 8) -> dict:
    """Exact recent error lines for one service (quote these as evidence)."""
    rows, source = _rows(minutes, [service])
    rows = [r for r in rows if r["service"] == service]
    hits = [r for r in rows if (contains.lower() in r["body"].lower() if contains
                                else _is_err(r["severity"], r["body"]))]
    return {"service": service, "source": source, "lines_scanned": len(rows), "matches": len(hits),
            "lines": [{"time": r["time"], "severity": r["severity"], "body": r["body"][:300],
                       **({"trace_id": r["trace_id"]} if r["trace_id"] else {})} for r in hits[:limit]]}


# backwards-compatible name
def analyse(containers: list, minutes: int = 5) -> dict:
    return error_summary(containers, minutes)
