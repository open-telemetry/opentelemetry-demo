# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from conftest import jaeger_resource_spans, jaeger_service_names, poll_until


def test_service_has_traces(jaeger_url, trace_service):
    """Verify that the service appears in Jaeger and has at least one trace."""

    def check():
        return trace_service in jaeger_service_names(jaeger_url)

    poll_until(check, f"service '{trace_service}' in Jaeger services list")

    def check_traces():
        return len(jaeger_resource_spans(jaeger_url, trace_service, num_traces=1)) > 0

    poll_until(check_traces, f"at least 1 trace for '{trace_service}' in Jaeger")
