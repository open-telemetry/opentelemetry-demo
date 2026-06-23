# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import requests

from conftest import poll_until


def test_service_has_traces(jaeger_url, trace_service):
    """Verify that the service appears in Jaeger and has at least one trace."""

    def check():
        resp = requests.get(f"{jaeger_url}/jaeger/ui/api/services", timeout=5)
        resp.raise_for_status()
        services = resp.json().get("data", [])
        return trace_service in services

    poll_until(check, f"service '{trace_service}' in Jaeger services list")

    def check_traces():
        resp = requests.get(
            f"{jaeger_url}/jaeger/ui/api/traces",
            params={"service": trace_service, "limit": 1, "lookback": "1h"},
            timeout=10,
        )
        resp.raise_for_status()
        traces = resp.json().get("data", [])
        return len(traces) > 0

    poll_until(check_traces, f"at least 1 trace for '{trace_service}' in Jaeger")
