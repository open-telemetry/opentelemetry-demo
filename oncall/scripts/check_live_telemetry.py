#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Live Telemetry Environment Diagnostic Tool.
Checks connectivity to live telemetry endpoints across the OpenTelemetry Demo:
- Prometheus (localhost:9090)
- Jaeger API (via frontend-proxy localhost:8080 or port 59521)
- OpenSearch (port 49234 or 9200)
- Flagd API (localhost:8080)
- Locust LoadGen (port 49233 or 8089)
"""

import os
import sys
import requests

PROMETHEUS_HOST = os.environ.get("PROMETHEUS_HOST", "localhost")
PROMETHEUS_PORT = os.environ.get("PROMETHEUS_PORT", "9090")
JAEGER_HOST = os.environ.get("JAEGER_HOST", "localhost")
JAEGER_PORT = os.environ.get("JAEGER_UI_PORT", "8080")
OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = os.environ.get("OPENSEARCH_PORT", "49234")
FLAGD_HOST = os.environ.get("FLAGD_UI_HOST", "localhost")
FLAGD_PORT = os.environ.get("FLAGD_UI_PORT", "8080")
LOCUST_HOST = os.environ.get("LOCUST_HOST", "localhost")
LOCUST_PORT = os.environ.get("LOCUST_PORT", "49233")


def check_endpoint(name: str, url: str) -> bool:
    try:
        resp = requests.get(url, timeout=3.0)
        if resp.status_code in (200, 301, 302):
            print(f"  [+] {name:<22}: ONLINE  ({url}) [HTTP {resp.status_code}]")
            return True
        else:
            print(f"  [-] {name:<22}: DEGRADED ({url}) [HTTP {resp.status_code}]")
            return False
    except Exception as e:
        print(f"  [x] {name:<22}: OFFLINE ({url}) - {type(e).__name__}")
        return False


def main():
    print("=" * 80)
    print("  OPENTELEMETRY DEMO: LIVE TELEMETRY INGRESS AUDIT")
    print("=" * 80)

    prom_ok = check_endpoint("Prometheus (Metrics)", f"http://{PROMETHEUS_HOST}:{PROMETHEUS_PORT}/api/v1/query?query=up")
    jaeger_ok = check_endpoint("Jaeger API (Traces)", f"http://{JAEGER_HOST}:{JAEGER_PORT}/jaeger/ui/api/v3/services")
    opensearch_ok = check_endpoint("OpenSearch (Logs)", f"http://{OPENSEARCH_HOST}:{OPENSEARCH_PORT}")
    flagd_ok = check_endpoint("Flagd Read API", f"http://{FLAGD_HOST}:{FLAGD_PORT}/feature/api/read")
    locust_ok = check_endpoint("Locust LoadGen", f"http://{LOCUST_HOST}:{LOCUST_PORT}")

    print("-" * 80)
    if prom_ok and jaeger_ok:
        print("  >> STATUS: LIVE TELEMETRY ACTIVE!")
        print("  >> The AI On-Call Agent will automatically pull real-time data from your running containers.")
    else:
        print("  >> STATUS: OFFLINE / SIMULATION MODE")
        print("  >> Endpoints are unreachable. The AI On-Call Agent will use recorded OpenTelemetry incident bundles.")
    print("=" * 80)


if __name__ == "__main__":
    main()
