from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import HOST_FALLBACK_URLS, OPENSEARCH_URL


def _get_opensearch_client() -> tuple[httpx.Client, str]:
    urls = [OPENSEARCH_URL, HOST_FALLBACK_URLS.get("opensearch", "http://localhost:64368")]
    for url in urls:
        try:
            client = httpx.Client(timeout=10.0)
            resp = client.get(f"{url}/")
            if resp.status_code == 200:
                return client, url
            client.close()
        except Exception:
            pass
    return httpx.Client(timeout=10.0), urls[0]


def search_logs(
    service: str,
    severity: str = "",
    text: str = "",
    lookback_min: int = 15,
    limit: int = 10,
) -> str:
    if not service or not isinstance(service, str):
        return "Error: service name must be a non-empty string."

    service = service.strip()
    # HARD RULE 1: Never use flagd service logs as evidence!
    if service in ("flagd", "flagd-ui"):
        return "Error: Access to flagd/flagd-ui logs is prohibited by Hard Rule 1."

    client, base_url = _get_opensearch_client()
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=max(1, lookback_min))

    must_clauses: list[dict[str, Any]] = [
        {"range": {"@timestamp": {"gte": start.isoformat()}}},
        {"match": {"resource.service.name": service}},
    ]

    if severity:
        sev = severity.strip().lower()
        if sev in ("error", "err", "fatal"):
            must_clauses.append({"range": {"severity.number": {"gte": 17}}})
        elif sev in ("warn", "warning"):
            must_clauses.append({"range": {"severity.number": {"gte": 13}}})
        else:
            must_clauses.append({"match": {"severity.text": sev}})

    if text:
        must_clauses.append({"match": {"body": text.strip()}})

    query_body = {
        "size": max(limit * 3, 20),
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {"bool": {"must": must_clauses}},
    }

    try:
        resp = client.post(f"{base_url}/otel-logs-*/_search", json=query_body)
        if resp.status_code != 200:
            return f"OpenSearch error HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
    except Exception as e:
        return f"Error querying OpenSearch logs: {e}"
    finally:
        client.close()

    hits = data.get("hits", {}).get("hits", [])
    if not hits:
        criteria = f"service='{service}'"
        if severity:
            criteria += f", severity='{severity}'"
        if text:
            criteria += f", text='{text}'"
        return f"No logs found matching {criteria} in the last {lookback_min}m."

    counts: Counter[str] = Counter()
    first_seen: dict[str, str] = {}
    last_seen: dict[str, str] = {}
    trace_ids: dict[str, str] = {}
    severities: dict[str, str] = {}

    for hit in hits:
        src = hit.get("_source", {})
        body = str(src.get("body", "")).strip()
        ts = src.get("@timestamp", "")
        tid = src.get("traceId", "")
        sev_obj = src.get("severity", {})
        sev_txt = sev_obj.get("text", "INFO") if isinstance(sev_obj, dict) else str(sev_obj)

        counts[body] += 1
        if body not in last_seen:
            last_seen[body] = ts
            trace_ids[body] = tid
            severities[body] = sev_txt
        first_seen[body] = ts

    lines = [f"Logs for {service} (lookback {lookback_min}m, {len(hits)} total hits):", ""]
    for body, count in counts.most_common(limit):
        ts = last_seen.get(body, "")
        time_short = ts[11:19] if len(ts) >= 19 else ts
        sev_tag = severities.get(body, "INFO")
        tid = trace_ids.get(body)
        trace_str = f" [trace: {tid[:12]}]" if tid else ""
        count_str = f" (x{count})" if count > 1 else ""
        lines.append(f"[{time_short}] [{sev_tag}] {body}{count_str}{trace_str}")

    out = "\n".join(lines)
    return out[:2000]
