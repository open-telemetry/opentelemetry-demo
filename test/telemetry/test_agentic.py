# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Agent-specific telemetry assertions.

These tests supplement the parametrised trace/metric/log checks in
test_traces.py / test_metrics.py / test_logs.py.  They only run when
TEST_SCOPE=agentic and verify telemetry that is unique to the agentic
service graph (e.g. the LangGraph workflow span emitted by Traceloop).
"""

import os

import pytest
import requests

from conftest import poll_until

TEST_SCOPE = os.environ.get("TEST_SCOPE", "minimal")


def _find_span_by_operation(traces, operation_fragment: str) -> bool:
    """Return True if any span in the trace list contains *operation_fragment*."""
    for trace in traces:
        for span in trace.get("spans", []):  # Jaeger returns spans as a list
            if operation_fragment in span.get("operationName", ""):
                return True
    return False


@pytest.mark.skipif(TEST_SCOPE != "agentic", reason="agentic scope only")
def test_agent_has_workflow_span(jaeger_url):
    """Verify the Traceloop @workflow decorator emits an
    'astronomy_shop_agent_workflow' span that reaches Jaeger."""

    def check():
        resp = requests.get(
            f"{jaeger_url}/jaeger/ui/api/traces",
            params={"service": "agent", "limit": 20, "lookback": "1h"},
            timeout=10,
        )
        resp.raise_for_status()
        traces = resp.json().get("data", [])
        return _find_span_by_operation(traces, "astronomy_shop_agent_workflow")

    poll_until(
        check,
        "span containing 'astronomy_shop_agent_workflow' in Jaeger for service 'agent'",
    )
