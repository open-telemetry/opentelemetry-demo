# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import requests

from conftest import poll_until


def _trace_has_edge(trace, parent_service, child_service):
    """Return True if `trace` contains a span whose process.serviceName is
    `parent_service` and which has a direct child span whose process.serviceName
    is `child_service`. Matches via CHILD_OF references (preferred) or the
    legacy parentSpanID field."""
    processes = trace.get("processes", {})
    spans = trace.get("spans", [])
    parent_span_ids = {
        s["spanID"]
        for s in spans
        if processes.get(s.get("processID"), {}).get("serviceName") == parent_service
    }
    if not parent_span_ids:
        return False
    for s in spans:
        parent_id = None
        for ref in s.get("references", []):
            if ref.get("refType") == "CHILD_OF":
                parent_id = ref.get("spanID")
                break
        if parent_id is None:
            parent_id = s.get("parentSpanID")
        if parent_id and parent_id in parent_span_ids:
            child_svc = processes.get(s.get("processID"), {}).get("serviceName")
            if child_svc == child_service:
                return True
    return False


def test_service_edge_exists(jaeger_url, service_edge):
    """Verify a directed parent->child span relationship appears in Jaeger."""
    parent, child = service_edge

    # Query traces by the *child* service: any trace that has a child span will
    # also contain the parent span context, since the child carries the parent
    # ref. Querying by parent is unreliable because high-volume parent services
    # (e.g. frontend) produce many traces that never reach a given child within
    # the limit window.
    def check():
        resp = requests.get(
            f"{jaeger_url}/jaeger/ui/api/traces",
            params={"service": child, "limit": 20, "lookback": "1h"},
            timeout=10,
        )
        resp.raise_for_status()
        for trace in resp.json().get("data", []):
            if _trace_has_edge(trace, parent, child):
                return True
        return False

    poll_until(check, f"trace edge '{parent}->{child}' in Jaeger")
