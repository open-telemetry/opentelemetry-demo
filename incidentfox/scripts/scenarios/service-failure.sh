#!/bin/bash
# Description: Trigger payment service failures

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="paymentFailure"
FAILURE_RATE="${1:-50%}"  # Default to 50% failure rate

# Validate failure rate
case "$FAILURE_RATE" in
    10%|25%|50%|75%|90%|100%)
        ;;
    *)
        echo "❌ Invalid failure rate: $FAILURE_RATE"
        echo "Valid options: 10%, 25%, 50%, 75%, 90%, 100%"
        exit 1
        ;;
esac

echo "💳 Triggering payment service failures (rate: ${FAILURE_RATE})..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag with specified failure rate
jq ".flags.${FLAG_NAME}.defaultVariant = \"${FAILURE_RATE}\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to '${FAILURE_RATE}'"
echo ""
echo "Expected behavior:"
echo "  • ${FAILURE_RATE} of payment requests will fail with HTTP 500"
echo "  • Checkout operations will fail"
echo "  • Error traces will appear in Jaeger"
echo "  • Error logs will appear in OpenSearch"
echo ""
echo "Monitor:"
echo "  • Error rate: rate(http_server_requests_total{service_name=\"payment\",http_status_code=~\"5..\"}[5m])"
echo "  • Logs: docker compose logs payment | grep ERROR"
echo "  • Traces: http://localhost:16686/search?service=payment&tags={\"error\":\"true\"}"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

