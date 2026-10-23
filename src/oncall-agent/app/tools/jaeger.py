from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import HOST_FALLBACK_URLS, JAEGER_URL


def _get_jaeger_client() -> tuple[httpx.Client, str]:
    urls = [JAEGER_URL, HOST_FALLBACK_URLS.get("jaeger", "http://localhost:64371")]
    for url in urls:
        try:
            client = httpx.Client(timeout=10.0)
            resp = client.get(f"{url}/jaeger/ui/api/v3/services")
            if resp.status_code == 200:
                return client, url
            client.close()
        except Exception:
            pass
    return httpx.Client(timeout=10.0), urls[0]


def search_traces(
    service: str,
    error_only: bool = False,
    min_duration_ms: int = 0,
    lookback_min: int = 15,
    limit: int = 5,
) -> str:
    if not service or not isinstance(service, str):
        return "Error: service name must be a non-empty string."

    client, base_url = _get_jaeger_client()
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=max(1, lookback_min))

    params = {
        "query.serviceName": service,
        "query.startTimeMin": start.isoformat(),
        "query.startTimeMax": now.isoformat(),
        "query.numTraces": str(max(limit * 2, 10)),
    }

    try:
        resp = client.get(f"{base_url}/jaeger/ui/api/v3/trace-summaries", params=params)
        if resp.status_code != 200:
            return f"Jaeger error HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
    except Exception as e:
        return f"Error contacting Jaeger API: {e}"
    finally:
        client.close()

    summaries = data.get("summaries", [])
    if not summaries:
        return f"No traces found for service '{service}' in the last {lookback_min} minutes."

    matched_traces: list[dict[str, Any]] = []
    for s in summaries:
        tid = s.get("traceId", "")
        root_op = s.get("rootOperationName", "unknown")
        root_svc = s.get("rootServiceName", "unknown")
        try:
            start_nano = int(s.get("minStartTimeUnixNano", 0))
            end_nano = int(s.get("maxEndTimeUnixNano", 0))
            duration_ms = max(0.0, (end_nano - start_nano) / 1_000_000.0)
        except (ValueError, TypeError):
            duration_ms = 0.0

        if min_duration_ms > 0 and duration_ms < min_duration_ms:
            continue

        span_count = s.get("spanCount", 0)
        services = [sv.get("name") for sv in s.get("services", []) if sv.get("name")]

        has_error = False
        error_info = ""

        if error_only:
            try:
                t_client, _ = _get_jaeger_client()
                t_resp = t_client.get(f"{base_url}/jaeger/ui/api/v3/traces/{tid}")
                if t_resp.status_code == 200:
                    t_data = t_resp.json().get("result", {})
                    for rs in t_data.get("resourceSpans", []):
                        rs_svc = "unknown"
                        for rattr in rs.get("resource", {}).get("attributes", []):
                            if rattr.get("key") == "service.name":
                                rs_svc = rattr.get("value", {}).get("stringValue", "unknown")
                        for ss in rs.get("scopeSpans", []):
                            for sp in ss.get("spans", []):
                                st = sp.get("status", {})
                                code = st.get("code")
                                if code in (2, "STATUS_CODE_ERROR", "2"):
                                    has_error = True
                                    msg = st.get("message") or sp.get("name")
                                    error_info = f"{rs_svc}:{msg}"
                                    break
                t_client.close()
            except Exception:
                pass
            if not has_error:
                continue

        matched_traces.append({
            "trace_id": tid,
            "root_op": f"{root_svc}/{root_op}",
            "duration_ms": duration_ms,
            "span_count": span_count,
            "services": services[:4],
            "error_info": error_info,
        })

        if len(matched_traces) >= limit:
            break

    if not matched_traces:
        if error_only:
            return f"No error traces found for service '{service}' in the last {lookback_min}m."
        return f"No traces matching duration >= {min_duration_ms}ms found for service '{service}'."

    lines = [f"Traces for {service} (lookback {lookback_min}m):", ""]
    for t in matched_traces:
        err_str = f" [ERROR: {t['error_info']}]" if t["error_info"] else ""
        lines.append(
            f"- Trace {t['trace_id']}: {t['root_op']} ({t['duration_ms']:.1f}ms, {t['span_count']} spans){err_str}"
        )

    out = "\n".join(lines)
    return out[:2000]


def get_trace(trace_id: str) -> str:
    if not trace_id or not isinstance(trace_id, str):
        return "Error: trace_id must be a non-empty string."

    trace_id = trace_id.strip()
    client, base_url = _get_jaeger_client()
    try:
        resp = client.get(f"{base_url}/jaeger/ui/api/v3/traces/{trace_id}")
        if resp.status_code == 404:
            return f"Trace '{trace_id}' not found."
        if resp.status_code != 200:
            return f"Jaeger error HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
    except Exception as e:
        return f"Error contacting Jaeger API: {e}"
    finally:
        client.close()

    result = data.get("result", {})
    resource_spans = result.get("resourceSpans", [])
    if not resource_spans:
        return f"Trace '{trace_id}' has no span data."

    parsed_spans: list[dict[str, Any]] = []
    deepest_error_span: dict[str, Any] | None = None

    for rs in resource_spans:
        service_name = "unknown"
        for rattr in rs.get("resource", {}).get("attributes", []):
            if rattr.get("key") == "service.name":
                service_name = rattr.get("value", {}).get("stringValue", "unknown")

        for ss in rs.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                span_id = sp.get("spanId", "")
                parent_id = sp.get("parentSpanId", "")
                name = sp.get("name", "")
                status = sp.get("status", {})
                code = status.get("code", 0)
                is_error = code in (2, "STATUS_CODE_ERROR", "2")
                error_msg = status.get("message", "")

                start_nano = int(sp.get("startTimeUnixNano", 0))
                end_nano = int(sp.get("endTimeUnixNano", 0))
                duration_ms = max(0.0, (end_nano - start_nano) / 1_000_000.0)

                clean_attrs: dict[str, Any] = {}
                for attr in sp.get("attributes", []):
                    k = attr.get("key", "")
                    # HARD RULE 1: Never leak feature_flag.* attributes to agent!
                    if k.startswith("feature_flag") or "feature_flag" in k:
                        continue
                    if any(prefix in k for prefix in ("http", "rpc", "db", "error", "exception")):
                        v_obj = attr.get("value", {})
                        v = (
                            v_obj.get("stringValue")
                            or v_obj.get("intValue")
                            or v_obj.get("boolValue")
                            or v_obj.get("doubleValue")
                        )
                        clean_attrs[k] = v

                span_info = {
                    "span_id": span_id,
                    "parent_id": parent_id,
                    "service": service_name,
                    "name": name,
                    "duration_ms": duration_ms,
                    "is_error": is_error,
                    "error_msg": error_msg,
                    "attributes": clean_attrs,
                }
                parsed_spans.append(span_info)
                if is_error:
                    deepest_error_span = span_info

    lines = [f"Trace: {trace_id} ({len(parsed_spans)} spans total)", ""]
    if deepest_error_span:
        lines.append(
            f"⚠️ Leaf Error Span: [{deepest_error_span['service']}] {deepest_error_span['name']} ({deepest_error_span['duration_ms']:.1f}ms)"
        )
        if deepest_error_span["error_msg"]:
            lines.append(f"   Message: {deepest_error_span['error_msg']}")
        if deepest_error_span["attributes"]:
            attr_summary = ", ".join(f"{k}={v}" for k, v in list(deepest_error_span["attributes"].items())[:4])
            lines.append(f"   Attrs: {attr_summary}")
        lines.append("")

    lines.append("Call Path:")
    for s in parsed_spans[:12]:
        status_tag = " [ERROR]" if s["is_error"] else ""
        lines.append(f"- [{s['service']}] {s['name']} ({s['duration_ms']:.1f}ms){status_tag}")
        if s["attributes"]:
            relevant = {
                k: v
                for k, v in s["attributes"].items()
                if any(x in k for x in ("http.status_code", "rpc.grpc.status_code", "db.system", "exception.type"))
            }
            if relevant:
                lines.append(f"    {relevant}")

    if len(parsed_spans) > 12:
        lines.append(f"... ({len(parsed_spans) - 12} additional spans truncated)")

    out = "\n".join(lines)
    return out[:2000]
