# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import requests

from conftest import poll_until


def test_service_has_logs(opensearch_url, log_service):
    """Verify that the service has logs in OpenSearch."""

    def check():
        ppl = f"source=otel-logs-* | where resource.service.name = '{log_service}' | stats count()"
        resp = requests.post(
            f"{opensearch_url}/_plugins/_ppl",
            json={"query": ppl},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("datarows", [])
        return len(rows) > 0 and rows[0][0] > 0

    poll_until(check, f"logs for '{log_service}' in OpenSearch")
