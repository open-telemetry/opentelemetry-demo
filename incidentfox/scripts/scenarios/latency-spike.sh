#!/bin/bash
# Description: Trigger slow image loading (latency spike)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="imageSlowLoad"
DELAY="${1:-5sec}"  # Default to 5 second delay

# Validate delay
case "$DELAY" in
    5sec|10sec)
        ;;
    *)
        echo "❌ Invalid delay: $DELAY"
        echo "Valid options: 5sec, 10sec"
        exit 1
        ;;
esac

echo "🐌 Triggering latency spike in image-provider (delay: ${DELAY})..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag with specified delay
jq ".flags.${FLAG_NAME}.defaultVariant = \"${DELAY}\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to '${DELAY}'"
echo ""
echo "Expected behavior:"
echo "  • Images will load very slowly (${DELAY} delay)"
echo "  • Page load times will increase significantly"
echo "  • Users may experience timeouts"
echo "  • P95/P99 latencies will spike"
echo ""
echo "Monitor:"
echo "  • Latency: histogram_quantile(0.99, rate(http_server_duration_bucket{service_name=\"image-provider\"}[5m]))"
echo "  • Test: open http://localhost:8080 and watch images load"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

