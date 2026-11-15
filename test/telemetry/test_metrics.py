# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import requests

from conftest import poll_until


def test_service_has_metrics(prometheus_url, metric_service):
    """Verify that the service has metrics in Prometheus."""

    def check():
        query = f'target_info{{service_name="{metric_service}"}}'
        resp = requests.get(
            f"{prometheus_url}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json().get("data", {}).get("result", [])
        return len(result) > 0

    poll_until(check, f"metrics for '{metric_service}' in Prometheus")
