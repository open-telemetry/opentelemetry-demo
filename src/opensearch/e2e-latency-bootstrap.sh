#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# One-shot bootstrap for the E2E latency probe (prototype).
#
# Registers an OpenSearch ingest pipeline and index template that compute
# end-to-end pipeline latency for synthetic probe logs (see
# e2e-latency-ingest-pipeline.json). Runs once after OpenSearch is healthy,
# then exits.

set -eu

OPENSEARCH_URL="${OPENSEARCH_URL:-http://opensearch:9200}"
PIPELINE_ID="e2e-latency-probe"
TEMPLATE_ID="otel-logs-e2e-latency"
DIR="$(dirname "$0")"

echo "[e2e-latency-init] waiting for OpenSearch at ${OPENSEARCH_URL}"
until curl -sf "${OPENSEARCH_URL}/_cluster/health" >/dev/null 2>&1; do
  sleep 2
done
echo "[e2e-latency-init] OpenSearch reachable"

curl -sf -X PUT "${OPENSEARCH_URL}/_ingest/pipeline/${PIPELINE_ID}" \
  -H 'Content-Type: application/json' \
  --data-binary "@${DIR}/e2e-latency-ingest-pipeline.json" >/dev/null
echo "[e2e-latency-init] ingest pipeline '${PIPELINE_ID}' registered"

curl -sf -X PUT "${OPENSEARCH_URL}/_index_template/${TEMPLATE_ID}" \
  -H 'Content-Type: application/json' \
  --data-binary "@${DIR}/e2e-latency-index-template.json" >/dev/null
echo "[e2e-latency-init] index template '${TEMPLATE_ID}' registered"

# Apply to any otel-logs index that already exists (the template only covers
# indices created after it). Ignore failures when no index exists yet.
curl -s -X PUT \
  "${OPENSEARCH_URL}/otel-logs-*/_settings?allow_no_indices=true&ignore_unavailable=true" \
  -H 'Content-Type: application/json' \
  -d "{\"index.default_pipeline\":\"${PIPELINE_ID}\"}" >/dev/null || true
echo "[e2e-latency-init] bootstrap complete"
