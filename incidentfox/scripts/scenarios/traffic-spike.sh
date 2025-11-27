#!/bin/bash
# Description: Trigger load generator traffic spike

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="loadGeneratorFloodHomepage"

echo "🌊 Triggering traffic spike (homepage flood)..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • Load generator will flood the homepage"
echo "  • Massive increase in request rate"
echo "  • Increased latency across all services"
echo "  • Resource usage spike"
echo "  • Possible rate limiting"
echo ""
echo "Monitor:"
echo "  • Request rate: sum(rate(http_server_requests_total[1m]))"
echo "  • Latency: histogram_quantile(0.99, sum(rate(http_server_duration_bucket[5m])) by (le))"
echo "  • Resources: docker stats"
echo "  • Load gen: http://localhost:8080/loadgen"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

