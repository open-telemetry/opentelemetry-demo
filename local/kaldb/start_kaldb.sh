#!/usr/bin/env bash
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KALDB_HOME="${KALDB_HOME:-/Users/suman/code/kaldb-kaldb}"
KALDB_MANAGER_URL="${KALDB_MANAGER_URL:-http://localhost:8083}"
KALDB_PREPROCESSOR_URL="${KALDB_PREPROCESSOR_URL:-http://localhost:8086}"
KALDB_CLEAN="${KALDB_CLEAN:-false}"
KALDB_COMPOSE_FILE="${KALDB_COMPOSE_FILE:-$KALDB_HOME/docker-compose.yml:$ROOT_DIR/local/kaldb/docker-compose.kaldb-min-partitions.yaml}"
MANAGER_MIN_NUMBER_OF_PARTITIONS="${ASTRA_MANAGER_API_MIN_NUMBER_OF_PARTITIONS:-1}"
LOG_DATASET="${KALDB_LOG_DATASET:-otel-demo-logs}"
TRACE_DATASET="${KALDB_TRACE_DATASET:-otel-demo-traces}"
DATASET_THROUGHPUT_BYTES="${KALDB_DATASET_THROUGHPUT_BYTES:-4000000}"
PARTITION_MAX_CAPACITY_BYTES="${KALDB_PARTITION_MAX_CAPACITY_BYTES:-1000000000}"
KAFKA_TOPIC="${KALDB_KAFKA_TOPIC:-test-topic}"
KAFKA_BOOTSTRAP_SERVER="${KALDB_KAFKA_BOOTSTRAP_SERVER:-localhost:9092}"
LOG_PARTITION_IDS=(${KALDB_LOG_PARTITION_IDS:-0})
TRACE_PARTITION_IDS=(${KALDB_TRACE_PARTITION_IDS:-1})
PARTITION_IDS=()
MAX_PARTITION_ID=-1

for partition_id in "${LOG_PARTITION_IDS[@]}" "${TRACE_PARTITION_IDS[@]}"; do
  if [[ ! "$partition_id" =~ ^[0-9]+$ ]]; then
    echo "KalDB partition IDs must be numeric for Kafka partition routing: $partition_id" >&2
    exit 1
  fi

  if [[ " ${PARTITION_IDS[*]-} " != *" $partition_id "* ]]; then
    PARTITION_IDS+=("$partition_id")
  fi

  if (( 10#$partition_id > MAX_PARTITION_ID )); then
    MAX_PARTITION_ID=$((10#$partition_id))
  fi
done
KAFKA_PARTITION_COUNT="${KALDB_KAFKA_PARTITION_COUNT:-$((MAX_PARTITION_ID + 1))}"
LOG_INDEX_PARTITION="${KALDB_LOG_INDEX_PARTITION:-${LOG_PARTITION_IDS[0]}}"
TRACE_INDEX_PARTITION="${KALDB_TRACE_INDEX_PARTITION:-${TRACE_PARTITION_IDS[0]}}"

if [[ ! -d "$KALDB_HOME" ]]; then
  echo "KALDB_HOME does not exist: $KALDB_HOME" >&2
  exit 1
fi

wait_for_http() {
  local name="$1"
  local url="$2"
  local max_attempts="${3:-60}"
  local sleep_secs="${4:-2}"

  echo "Waiting for $name at $url ..."
  for attempt in $(seq 1 "$max_attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name is ready."
      return 0
    fi
    sleep "$sleep_secs"
  done

  echo "$name did not become ready in time." >&2
  exit 1
}

create_dataset() {
  local name="$1"
  local pattern="$2"
  local partition_ids=("${@:3}")
  local partition_ids_json

  echo "Ensuring KalDB dataset $name with serviceNamePattern $pattern ..."
  curl -fsS -XPOST \
    -H 'content-type: application/json; charset=utf-8; protocol=gRPC' \
    "$KALDB_MANAGER_URL/slack.proto.astra.ManagerApiService/CreateDatasetMetadata" \
    -d "{
      \"name\": \"$name\",
      \"owner\": \"otel-demo@localhost\",
      \"serviceNamePattern\": \"$pattern\"
    }" >/dev/null || echo "Dataset $name may already exist."

  curl -fsS -XPOST \
    -H 'content-type: application/json; charset=utf-8; protocol=gRPC' \
    "$KALDB_MANAGER_URL/slack.proto.astra.ManagerApiService/UpdateDatasetMetadata" \
    -d "{
      \"name\": \"$name\",
      \"owner\": \"otel-demo@localhost\",
      \"serviceNamePattern\": \"$pattern\"
    }" >/dev/null

  partition_ids_json="$(partition_ids_json "${partition_ids[@]}")"
  curl -fsS -XPOST \
    -H 'content-type: application/json; charset=utf-8; protocol=gRPC' \
    "$KALDB_MANAGER_URL/slack.proto.astra.ManagerApiService/UpdatePartitionAssignment" \
    -d "{
      \"name\": \"$name\",
      \"throughputBytes\": \"$DATASET_THROUGHPUT_BYTES\",
      \"partitionIds\": $partition_ids_json
    }" >/dev/null
}

partition_ids_json() {
  local json="["
  local separator=""

  for partition_id in "$@"; do
    json="$json$separator\"$partition_id\""
    separator=","
  done

  echo "$json]"
}

create_partition() {
  local partition_id="$1"

  echo "Ensuring KalDB partition $partition_id with max capacity $PARTITION_MAX_CAPACITY_BYTES ..."
  curl -fsS -XPOST \
    -H 'content-type: application/json; charset=utf-8; protocol=gRPC' \
    "$KALDB_MANAGER_URL/slack.proto.astra.ManagerApiService/CreatePartition" \
    -d "{
      \"partitionId\": \"$partition_id\",
      \"maxCapacity\": \"$PARTITION_MAX_CAPACITY_BYTES\"
    }" >/dev/null || echo "Partition $partition_id may already exist."
}

ensure_kafka_partitions() {
  echo "Ensuring Kafka topic $KAFKA_TOPIC has at least $KAFKA_PARTITION_COUNT partitions ..."
  docker exec dep_kafka kafka-topics.sh \
    --alter \
    --topic "$KAFKA_TOPIC" \
    --partitions "$KAFKA_PARTITION_COUNT" \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" || \
    echo "Kafka topic $KAFKA_TOPIC may already have at least $KAFKA_PARTITION_COUNT partitions."
}

run_quick_start() {
  local args=()

  if [[ "$KALDB_CLEAN" == "true" ]]; then
    args+=(--clean)
  fi

  (
    cd "$KALDB_HOME"
    COMPOSE_FILE="$KALDB_COMPOSE_FILE" \
      ASTRA_MANAGER_API_MIN_NUMBER_OF_PARTITIONS="$MANAGER_MIN_NUMBER_OF_PARTITIONS" \
	      OTEL_DEMO_HOME="$ROOT_DIR" \
	      KALDB_LOG_DATASET="$LOG_DATASET" \
	      KALDB_TRACE_DATASET="$TRACE_DATASET" \
	      KALDB_KAFKA_PARTITION_COUNT="$KAFKA_PARTITION_COUNT" \
      KALDB_LOG_INDEX_PARTITION="$LOG_INDEX_PARTITION" \
      KALDB_TRACE_INDEX_PARTITION="$TRACE_INDEX_PARTITION" \
      ./quick_start.sh ${args[@]+"${args[@]}"}
  )
}

echo "Starting KalDB from $KALDB_HOME ..."
run_quick_start
ensure_kafka_partitions

wait_for_http "KalDB Manager API" "$KALDB_MANAGER_URL/health"
wait_for_http "KalDB Preprocessor" "$KALDB_PREPROCESSOR_URL/health"

for partition_id in "${PARTITION_IDS[@]}"; do
  create_partition "$partition_id"
done

create_dataset "$LOG_DATASET" "$LOG_DATASET" "${LOG_PARTITION_IDS[@]}"
create_dataset "$TRACE_DATASET" "$TRACE_DATASET" "${TRACE_PARTITION_IDS[@]}"

echo ""
echo "KalDB is ready for the OpenTelemetry Demo."
echo "  Logs dataset:   $LOG_DATASET"
echo "  Traces dataset: $TRACE_DATASET"
echo "  Log partitions: ${LOG_PARTITION_IDS[*]}"
echo "  Trace partitions: ${TRACE_PARTITION_IDS[*]}"
echo "  Query API:      http://localhost:8081"
echo "  Grafana:        http://localhost:3000/d/kaldb-otel-demo/kaldb-otel-demo"
echo "  Dashboards:     http://localhost:5601/app/discover"
