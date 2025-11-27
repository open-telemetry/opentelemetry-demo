#!/bin/bash
# Description: Trigger Kafka message queue lag

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="kafkaQueueProblems"

echo "📊 Triggering Kafka queue lag..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • Kafka producers will flood the queue"
echo "  • Consumers will slow down, causing lag"
echo "  • Order processing will be delayed"
echo "  • Accounting and fraud-detection will fall behind"
echo ""
echo "Monitor:"
echo "  • Kafka lag: kafka_consumer_lag"
echo "  • Queue depth: kafka_server_log_logendoffset - kafka_consumer_currentoffset"
echo "  • Consumer logs: docker compose logs accounting fraud-detection"
echo ""
echo "⚠️  May take 5-10 minutes for consumers to catch up after disabling"
echo "To disable: ./trigger-incident.sh clear-all"

