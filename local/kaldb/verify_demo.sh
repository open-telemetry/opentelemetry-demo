#!/usr/bin/env bash
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

DEMO_URL="${DEMO_URL:-http://localhost:18080}"
KALDB_MANAGER_URL="${KALDB_MANAGER_URL:-http://localhost:8083}"
KALDB_PREPROCESSOR_URL="${KALDB_PREPROCESSOR_URL:-http://localhost:8086}"
KALDB_QUERY_URL="${KALDB_QUERY_URL:-http://localhost:8081}"

check_http() {
  local name="$1"
  local url="$2"

  printf "Checking %s ... " "$name"
  curl -fsS "$url" >/dev/null
  echo "ok"
}

check_http "OpenTelemetry Demo UI" "$DEMO_URL"
check_http "KalDB Manager API" "$KALDB_MANAGER_URL/health"
check_http "KalDB Preprocessor" "$KALDB_PREPROCESSOR_URL/health"
check_http "KalDB Query API" "$KALDB_QUERY_URL/"

echo ""
echo "Demo endpoints are reachable."
echo "Generate traffic at $DEMO_URL, then inspect:"
echo "  Dashboard: http://localhost:3000/d/kaldb-otel-demo/kaldb-otel-demo"
echo "  Logs:      Dashboard log panel or Grafana Explore datasource otel-demo-logs"
echo "  Spans:     Dashboard log panel or Grafana Explore datasource otel-demo-traces"
echo "  Waterfall: Grafana Explore datasource otel-demo-traces-waterfall, query by trace ID"
