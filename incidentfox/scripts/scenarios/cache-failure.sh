#!/bin/bash
# Description: Trigger recommendation cache failures

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="recommendationCacheFailure"

echo "💾 Triggering cache failure in recommendation service..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • Recommendation cache will fail"
echo "  • Service will fall back to expensive operations"
echo "  • Latency will increase"
echo "  • CPU usage will increase"
echo "  • More calls to product-catalog service"
echo ""
echo "Monitor:"
echo "  • Latency: histogram_quantile(0.95, rate(http_server_duration_bucket{service_name=\"recommendation\"}[5m]))"
echo "  • Cache misses: rate(recommendation_cache_misses_total[5m])"
echo "  • Logs: docker compose logs recommendation"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

