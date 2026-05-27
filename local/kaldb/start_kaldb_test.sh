#!/usr/bin/env bash
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/bin" "$TMP_DIR/kaldb"

cat >"$TMP_DIR/kaldb/quick_start.sh" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

{
  echo "ASTRA_MANAGER_API_MIN_NUMBER_OF_PARTITIONS=${ASTRA_MANAGER_API_MIN_NUMBER_OF_PARTITIONS:-}"
  echo "COMPOSE_FILE=${COMPOSE_FILE:-}"
  echo "OTEL_DEMO_HOME=${OTEL_DEMO_HOME:-}"
  echo "KALDB_LOG_DATASET=${KALDB_LOG_DATASET:-}"
  echo "KALDB_TRACE_DATASET=${KALDB_TRACE_DATASET:-}"
} >"$KALDB_TEST_CAPTURE_DIR/quick_start_env"
SCRIPT
chmod +x "$TMP_DIR/kaldb/quick_start.sh"

cat >"$TMP_DIR/bin/curl" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

payload=""
url=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d)
      shift
      payload="$1"
      ;;
    http://*)
      url="$1"
      ;;
  esac
  shift || true
done

if [[ -n "$payload" ]]; then
  {
    echo "URL: $url"
    echo "$payload"
  } >>"$KALDB_TEST_CAPTURE_DIR/curl_payloads"
fi
SCRIPT
chmod +x "$TMP_DIR/bin/curl"

cat >"$TMP_DIR/bin/docker" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

echo "$*" >>"$KALDB_TEST_CAPTURE_DIR/docker_calls"
SCRIPT
chmod +x "$TMP_DIR/bin/docker"

KALDB_TEST_CAPTURE_DIR="$TMP_DIR" \
KALDB_HOME="$TMP_DIR/kaldb" \
KALDB_MANAGER_URL="http://manager" \
KALDB_PREPROCESSOR_URL="http://preprocessor" \
PATH="$TMP_DIR/bin:$PATH" \
"$ROOT_DIR/local/kaldb/start_kaldb.sh" >"$TMP_DIR/output"

require_contains() {
  local file="$1"
  local pattern="$2"

  if ! grep -Fq "$pattern" "$file"; then
    echo "Expected $file to contain: $pattern" >&2
    echo "--- $file ---" >&2
    cat "$file" >&2
    exit 1
  fi
}

require_not_contains() {
  local file="$1"
  local pattern="$2"

  if grep -Fq "$pattern" "$file"; then
    echo "Expected $file not to contain: $pattern" >&2
    echo "--- $file ---" >&2
    cat "$file" >&2
    exit 1
  fi
}

require_contains "$TMP_DIR/quick_start_env" "ASTRA_MANAGER_API_MIN_NUMBER_OF_PARTITIONS=1"
require_contains "$TMP_DIR/quick_start_env" "docker-compose.kaldb-min-partitions.yaml"
require_contains "$TMP_DIR/quick_start_env" "OTEL_DEMO_HOME=$ROOT_DIR"
require_contains "$TMP_DIR/quick_start_env" "KALDB_LOG_DATASET=otel-demo-logs"
require_contains "$TMP_DIR/quick_start_env" "KALDB_TRACE_DATASET=otel-demo-traces"
require_contains "$TMP_DIR/docker_calls" "exec dep_kafka kafka-topics.sh --alter --topic test-topic --partitions 2 --bootstrap-server localhost:9092"
require_contains "$TMP_DIR/curl_payloads" '"partitionId": "0"'
require_contains "$TMP_DIR/curl_payloads" '"partitionId": "1"'
require_contains "$TMP_DIR/curl_payloads" '"name": "otel-demo-logs"'
require_contains "$TMP_DIR/curl_payloads" '"partitionIds": ["0"]'
require_contains "$TMP_DIR/curl_payloads" '"name": "otel-demo-traces"'
require_contains "$TMP_DIR/curl_payloads" '"serviceNamePattern": "otel-demo-traces"'
require_contains "$TMP_DIR/curl_payloads" '"partitionIds": ["1"]'
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" "container_name: astra_index_1"
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" 'KAFKA_TOPIC_PARTITION: "${KALDB_TRACE_INDEX_PARTITION:-1}"'
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" 'INDEXER_MAX_MESSAGES_PER_CHUNK: "${KALDB_INDEXER_MAX_MESSAGES_PER_CHUNK:-10000000}"'
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" 'INDEXER_MAX_BYTES_PER_CHUNK: "${KALDB_INDEXER_MAX_BYTES_PER_CHUNK:-10000000000}"'
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" 'INDEXER_MAX_TIME_PER_CHUNK_SECONDS: "${KALDB_INDEXER_MAX_TIME_PER_CHUNK_SECONDS:-3600}"'
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" 'ASTRA_PREPROCESSOR_OTLP_TRACE_DATASET_NAME: "${KALDB_TRACE_DATASET:-otel-demo-traces}"'
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" 'S3_ENDPOINT: "http://s3:9090"'
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" "/etc/grafana/provisioning/datasources/kaldb-demo.yml"
require_contains "$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml" "/etc/grafana/provisioning/dashboards/kaldb-demo.yml"
require_contains "$ROOT_DIR/local/kaldb/grafana/provisioning/datasources/kaldb-demo.yml" "uid: otel-demo-logs"
require_contains "$ROOT_DIR/local/kaldb/grafana/provisioning/datasources/kaldb-demo.yml" "uid: otel-demo-traces"
require_contains "$ROOT_DIR/local/kaldb/grafana/provisioning/datasources/kaldb-demo.yml" "uid: otel-demo-traces-waterfall"
require_contains "$ROOT_DIR/local/kaldb/grafana/provisioning/datasources/kaldb-demo.yml" "type: grafana-opensearch-datasource"
require_contains "$ROOT_DIR/local/kaldb/grafana/provisioning/datasources/kaldb-demo.yml" "deleteDatasources:"
require_contains "$ROOT_DIR/local/kaldb/grafana/provisioning/datasources/kaldb-demo.yml" "tracesToLogsV2:"
require_contains "$ROOT_DIR/local/kaldb/grafana/provisioning/dashboards/kaldb-demo.yml" "/var/lib/grafana/dashboards/kaldb-demo"
require_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" "KalDB OTel Demo"
require_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '"type": "logs"'
require_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '"uid": "otel-demo-traces"'
require_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '\"datasource\":{\"type\":\"grafana-opensearch-datasource\",\"uid\":\"otel-demo-logs\"}'
require_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '\"datasource\":{\"type\":\"zipkin\",\"uid\":\"otel-demo-traces-waterfall\"}'
require_not_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '"type": "raw_document"'
require_not_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '"type": "elasticsearch"'
require_not_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '\"datasource\":\"kaldb-logs\"'
require_not_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '\"datasource\":\"kaldb-trace-docs\"'
require_not_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" '\"datasource\":\"kaldb-traces\"'
require_not_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" "otel_logs"
require_not_contains "$ROOT_DIR/local/kaldb/grafana/dashboards/otel-demo-kaldb.json" "otel_traces"
require_contains "$ROOT_DIR/local/kaldb/compose.kaldb.yaml" "LOCUST_USERS: \"1\""
require_contains "$ROOT_DIR/local/kaldb/compose.kaldb.yaml" "LOCUST_BROWSER_TRAFFIC_ENABLED: \"false\""
require_contains "$ROOT_DIR/local/kaldb/compose.kaldb.yaml" "./local/kaldb/otelcol-config-kaldb.yml:/etc/otelcol-config-kaldb.yml"

echo "start_kaldb partition allocation test passed"
