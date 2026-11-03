# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from conftest import jaeger_resource_spans, poll_until


def _resource_service_name(resource):
    for attr in resource.get("attributes", []):
        if attr.get("key") == "service.name":
            return attr.get("value", {}).get("stringValue")
    return None


def _edge_exists(resource_spans, parent_service, child_service):
    """Return True if a `child_service` span has a `parent_service` parent span
    within the same trace, across the v3 resourceSpans (grouped per service)."""
    span_service = {}
    child_parents = []
    for rs in resource_spans:
        service = _resource_service_name(rs.get("resource", {}))
        for scope_spans in rs.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                trace_id = span.get("traceId")
                span_service[(trace_id, span.get("spanId"))] = service
                parent_span_id = span.get("parentSpanId")
                if service == child_service and parent_span_id:
                    child_parents.append((trace_id, parent_span_id))
    return any(span_service.get(key) == parent_service for key in child_parents)


def test_service_edge_exists(jaeger_url, service_edge):
    """Verify a directed parent->child span relationship appears in Jaeger."""
    parent, child = service_edge

    # Query by the child service (traces carry the parent span too) with a
    # generous limit so rarely-called edges still appear within the window.
    def check():
        resource_spans = jaeger_resource_spans(jaeger_url, child, num_traces=200)
        return _edge_exists(resource_spans, parent, child)

    poll_until(check, f"trace edge '{parent}->{child}' in Jaeger")
