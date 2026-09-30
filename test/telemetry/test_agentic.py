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

from conftest import jaeger_resource_spans, poll_until

TEST_SCOPE = os.environ.get("TEST_SCOPE", "minimal")


def _find_span_by_name(resource_spans, name_fragment: str) -> bool:
    """Return True if any v3 OTLP span's name contains *name_fragment*."""
    for rs in resource_spans:
        for scope_spans in rs.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                if name_fragment in span.get("name", ""):
                    return True
    return False


@pytest.mark.skipif(TEST_SCOPE != "agentic", reason="agentic scope only")
def test_agent_has_workflow_span(jaeger_url):
    """Verify the Traceloop @workflow decorator emits an
    'astronomy_shop_agent_workflow' span that reaches Jaeger."""

    def check():
        resource_spans = jaeger_resource_spans(jaeger_url, "agent", num_traces=20)
        return _find_span_by_name(resource_spans, "astronomy_shop_agent_workflow")

    poll_until(
        check,
        "span containing 'astronomy_shop_agent_workflow' in Jaeger for service 'agent'",
    )
