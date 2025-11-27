#!/bin/bash
# Description: Make payment service unreachable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="paymentUnreachable"

echo "🚫 Making payment service unreachable..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • Payment service will not respond to requests"
echo "  • Checkout will timeout"
echo "  • All checkout attempts will fail"
echo "  • Circuit breakers may trigger"
echo ""
echo "Monitor:"
echo "  • Service status: up{service_name=\"payment\"}"
echo "  • Timeout errors: increase(http_client_request_duration_seconds_count{service_name=\"checkout\",error=\"timeout\"}[5m])"
echo "  • Logs: docker compose logs checkout | grep payment"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

