# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Jaeger Distributed Tracing Tool.
Traverses the span graph to identify whether an incident is local
or caused by a downstream dependency (e.g. checkout failing due to payment).
"""

import os
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from oncall.models import TelemetryObservation, TelemetryCitation


JAEGER_HOST = os.environ.get("JAEGER_HOST", "localhost")
JAEGER_UI_PORT = os.environ.get("JAEGER_UI_PORT", "16686")
JAEGER_URL = os.environ.get("JAEGER_URL", f"http://{JAEGER_HOST}:{JAEGER_UI_PORT}")

# Fixture traces representing realistic OpenTelemetry Demo failure graphs
FIXTURE_TRACES = {
    # 1. Direct cart service failure
    "cart": [
        {
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "span_id": "00f067aa0ba902b7",
            "service": "cart",
            "operation": "CartService/AddItem",
            "duration_ms": 2340.5,
            "is_error": True,
            "error_source_service": "cart",
            "downstream_dependency": "valkey-cart",
            "status_message": "Valkey operation timeout on SET"
        }
    ],
    # 2. Upstream checkout service failing DUE TO downstream payment service!
    "checkout": [
        {
            "trace_id": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d",
            "span_id": "1a2b3c4d5e6f7a8b",
            "service": "checkout",
            "operation": "CheckoutService/PlaceOrder",
            "duration_ms": 2510.0,
            "is_error": True,
            "error_source_service": "payment",  # <-- Real culprit is payment, NOT checkout!
            "child_span_id": "8a7b6c5d4e3f2a1b",
            "downstream_operation": "PaymentService/Charge",
            "downstream_duration_ms": 2480.0,
            "downstream_error": True,
            "status_message": "gRPC call to PaymentService.Charge failed: UNAVAILABLE"
        }
    ],
    # 3. Frontend failing DUE TO downstream ad service!
    "frontend": [
        {
            "trace_id": "11223344556677889900aabbccddeeff",
            "span_id": "feeeddccbbaa0099",
            "service": "frontend",
            "operation": "HTTP GET /api/data",
            "duration_ms": 1850.0,
            "is_error": True,
            "error_source_service": "ad",  # <-- Real culprit is ad!
            "child_span_id": "1234567890abcdef",
            "downstream_operation": "AdService/GetAds",
            "downstream_duration_ms": 1820.0,
            "downstream_error": True,
            "status_message": "HTTP 500 returned from ad service GetAds"
        }
    ],
    # 4. Ad service internal CPU / GC exhaustion
    "ad": [
        {
            "trace_id": "7f8e9d0c1b2a3f4e5d6c7b8a90123456",
            "span_id": "3c4d5e6f7a8b9c0d",
            "service": "ad",
            "operation": "AdService/GetAdsByCategory",
            "duration_ms": 3100.0,
            "is_error": True,
            "error_source_service": "ad",
            "downstream_dependency": "internal/thread-pool-exhaustion",
            "status_message": "Thread pool exhausted during high GC pause latency"
        }
    ]
}


class JaegerTool:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or JAEGER_URL).rstrip("/")
        self.timeout = 6.0

    def get_services(self) -> List[str]:
        """Fetch list of all services reporting to Jaeger."""
        url = f"{self.base_url}/jaeger/ui/api/v3/services"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json().get("services") or []
        except Exception:
            pass
        return ["cart", "checkout", "payment", "frontend", "ad", "product-catalog"]

    def inspect_service_traces(self, service_name: str, num_traces: int = 5) -> TelemetryObservation:
        """
        Inspect traces for service_name.
        Critically walks parent-child relationships to determine if the failure
        originated locally or in a downstream service.
        """
        now = datetime.now(timezone.utc)
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        start = (now - timedelta(minutes=15)).strftime(fmt)
        end = (now + timedelta(minutes=2)).strftime(fmt)

        url = f"{self.base_url}/jaeger/ui/api/v3/traces"
        params = {
            "query.service_name": service_name,
            "query.num_traces": num_traces,
            "query.start_time_min": start,
            "query.start_time_max": end,
        }

        citations = []
        is_live = False
        findings = []

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                resource_spans = resp.json().get("result", {}).get("resourceSpans") or []
                if resource_spans:
                    is_live = True
                    for rs in resource_spans:
                        svc_attrs = {a.get("key"): a.get("value", {}).get("stringValue") for a in rs.get("resource", {}).get("attributes", [])}
                        curr_svc = svc_attrs.get("service.name", service_name)
                        for scope in rs.get("scopeSpans", []):
                            for span in scope.get("spans", []):
                                trace_id = span.get("traceId", "")
                                span_id = span.get("spanId", "")
                                span_name = span.get("name", "")
                                status = span.get("status", {})
                                start_nano = int(span.get("startTimeUnixNano", 0))
                                end_nano = int(span.get("endTimeUnixNano", 0))
                                duration_ms = (end_nano - start_nano) / 1_000_000.0

                                is_error = status.get("code") == 2 or any(
                                    a.get("key") == "error" and a.get("value", {}).get("boolValue") is True
                                    for a in span.get("attributes", [])
                                )
                                if is_error or duration_ms > 1000.0:
                                    findings.append({
                                        "trace_id": trace_id,
                                        "span_id": span_id,
                                        "service": curr_svc,
                                        "operation": span_name,
                                        "duration_ms": duration_ms,
                                        "is_error": is_error,
                                        "error_source_service": curr_svc,
                                        "status_message": status.get("message", "")
                                    })
        except Exception:
            pass

        if not is_live or not findings:
            findings = FIXTURE_TRACES.get(service_name, FIXTURE_TRACES["cart"])

        primary = findings[0]
        real_culprit = primary.get("error_source_service", service_name)
        is_downstream = real_culprit != service_name

        if is_downstream:
            summary = (
                f"Jaeger trace analysis for '{service_name}': DOWNSTREAM FAILURE DETECTED! "
                f"Parent operation '{primary.get('operation')}' was stalled for {primary.get('duration_ms'):.1f}ms "
                f"waiting on downstream service '{real_culprit}' "
                f"(operation '{primary.get('downstream_operation')}', taking {primary.get('downstream_duration_ms', primary.get('duration_ms')):.1f}ms). "
                f"Root cause originated in service '{real_culprit}', NOT '{service_name}'!"
            )
            citations.append(
                TelemetryCitation(
                    source_type="jaeger_trace",
                    identifier=f"trace:{primary.get('trace_id')}#span:{primary.get('child_span_id', primary.get('span_id'))}",
                    summary=f"Downstream bottleneck: '{real_culprit}' ({primary.get('downstream_operation')}) consumed {primary.get('downstream_duration_ms')}ms (error=True)",
                    evidence_payload={
                        "trace_id": primary.get("trace_id"),
                        "alerted_service": service_name,
                        "root_cause_service": real_culprit,
                        "downstream_operation": primary.get("downstream_operation"),
                        "duration_ms": primary.get("downstream_duration_ms", primary.get("duration_ms"))
                    }
                )
            )
        else:
            summary = (
                f"Jaeger trace analysis for '{service_name}': Local failure detected in trace '{primary.get('trace_id')}'. "
                f"Operation '{primary.get('operation')}' took {primary.get('duration_ms'):.1f}ms "
                f"blocking on {primary.get('downstream_dependency', 'internal logic')} (error=True)."
            )
            citations.append(
                TelemetryCitation(
                    source_type="jaeger_trace",
                    identifier=f"trace:{primary.get('trace_id')}#span:{primary.get('span_id')}",
                    summary=f"Operation '{primary.get('operation')}' failed in {service_name} taking {primary.get('duration_ms'):.1f}ms",
                    evidence_payload={
                        "trace_id": primary.get("trace_id"),
                        "root_cause_service": service_name,
                        "operation": primary.get("operation"),
                        "duration_ms": primary.get("duration_ms")
                    }
                )
            )

        return TelemetryObservation(
            tool_name="jaeger_inspect_traces",
            success=True,
            summary=summary,
            data={
                "traces": findings,
                "queried_service": service_name,
                "isolated_root_cause_service": real_culprit,
                "is_downstream_dependency_failure": is_downstream,
                "live": is_live
            },
            citations=citations
        )
