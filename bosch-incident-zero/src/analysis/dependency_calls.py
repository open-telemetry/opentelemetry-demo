"""Find failing calls between services in raw Jaeger v3 (OTLP JSON) trace data.

A failing CLIENT/PRODUCER span from caller X to callee Y is a "frontier" call when
either Y never appears beneath it (Y was unreachable), or Y does appear and fails
without any failing outbound call of its own (the fault is inside Y). Calls whose
callee merely passes on a deeper failure are skipped: the deeper call explains them.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# OTLP span kinds as Jaeger v3 returns them (ints) or as strings.
_OUTBOUND_KINDS = {3, 4, "SPAN_KIND_CLIENT", "SPAN_KIND_PRODUCER"}
_ERROR_CODES = {2, "STATUS_CODE_ERROR"}

# gRPC service names in the demo's protos -> container/service names.
RPC_SERVICE_MAP: Dict[str, str] = {
    "AdService": "ad",
    "CartService": "cart",
    "CheckoutService": "checkout",
    "CurrencyService": "currency",
    "EmailService": "email",
    "PaymentService": "payment",
    "ProductCatalogService": "product-catalog",
    "RecommendationService": "recommendation",
    "ShippingService": "shipping",
    "QuoteService": "quote",
}
DB_SYSTEM_MAP: Dict[str, str] = {"redis": "valkey-cart", "valkey": "valkey-cart", "postgresql": "astronomy-db"}
MESSAGING_SYSTEM_MAP: Dict[str, str] = {"kafka": "kafka"}
HOST_SERVICES = set(RPC_SERVICE_MAP.values()) | {
    "frontend", "frontend-proxy", "image-provider", "accounting", "fraud-detection",
    "valkey-cart", "astronomy-db", "kafka", "flagd",
}

# "oteldemo.PaymentService/Charge" -> "PaymentService"
_RPC_NAME = re.compile(r"(?:^|\.)([A-Za-z]+Service)/")


def _attrs(span: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for a in span.get("attributes") or []:
        val = a.get("value") or {}
        out[a.get("key")] = next(iter(val.values()), None) if isinstance(val, dict) else val
    return out


def _service_of(resource_span: Dict[str, Any]) -> Optional[str]:
    for a in (resource_span.get("resource") or {}).get("attributes") or []:
        if a.get("key") == "service.name":
            return (a.get("value") or {}).get("stringValue")
    return None


def _host_service(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return None
    host = urlparse(value).hostname if "://" in value else value.split(":")[0]
    return host if host in HOST_SERVICES else None


def callee_of(span: Dict[str, Any]) -> Optional[str]:
    """Identify the service an outbound span calls, or None if it cannot be told."""
    attrs = _attrs(span)
    for key in ("rpc.service", "rpc.method"):
        val = attrs.get(key)
        if isinstance(val, str):
            name = val.split(".")[-1].split("/")[0]
            if name in RPC_SERVICE_MAP:
                return RPC_SERVICE_MAP[name]
    m = _RPC_NAME.search(span.get("name") or "")
    if m and m.group(1) in RPC_SERVICE_MAP:
        return RPC_SERVICE_MAP[m.group(1)]
    db = attrs.get("db.system") or attrs.get("db.system.name")
    if db in DB_SYSTEM_MAP:
        return DB_SYSTEM_MAP[db]
    msg = attrs.get("messaging.system")
    if msg in MESSAGING_SYSTEM_MAP:
        return MESSAGING_SYSTEM_MAP[msg]
    for key in ("peer.service", "server.address", "net.peer.name", "url.full", "http.url"):
        svc = _host_service(attrs.get(key))
        if svc:
            return svc
    return None


def _is_error(span: Dict[str, Any]) -> bool:
    return (span.get("status") or {}).get("code") in _ERROR_CODES


def find_failed_dependency_calls(raw: Any) -> List[Dict[str, Any]]:
    """Return frontier failing calls found in a Jaeger v3 /traces response."""
    if not isinstance(raw, dict):
        return []
    spans: Dict[str, Dict[str, Any]] = {}
    for rs in (raw.get("result") or {}).get("resourceSpans") or []:
        svc = _service_of(rs)
        for scope in rs.get("scopeSpans") or []:
            for span in scope.get("spans") or []:
                if span.get("spanId"):
                    spans[span["spanId"]] = {"service": svc, "span": span}

    children: Dict[str, List[str]] = {}
    for sid, entry in spans.items():
        parent = entry["span"].get("parentSpanId")
        if parent:
            children.setdefault(parent, []).append(sid)

    def descendants(sid: str) -> List[Dict[str, Any]]:
        out, stack = [], list(children.get(sid, []))
        while stack:
            cur = stack.pop()
            out.append(spans[cur])
            stack.extend(children.get(cur, []))
        return out

    calls: List[Dict[str, Any]] = []
    for sid, entry in spans.items():
        span, caller = entry["span"], entry["service"]
        if span.get("kind") not in _OUTBOUND_KINDS or not _is_error(span):
            continue
        callee = callee_of(span)
        if not callee or callee == caller:
            continue
        below = descendants(sid)
        callee_spans = [d for d in below if d["service"] == callee]
        reached = bool(callee_spans)
        callee_failed = any(_is_error(d["span"]) for d in callee_spans)
        passes_on = any(
            d["span"].get("kind") in _OUTBOUND_KINDS and _is_error(d["span"]) for d in callee_spans
        )
        if reached and (not callee_failed or passes_on):
            continue
        calls.append({
            "trace_id": span.get("traceId"),
            "caller": caller,
            "callee": callee,
            "operation": span.get("name"),
            "error": (span.get("status") or {}).get("message") or "",
            "callee_reached": reached,
        })
    return calls
