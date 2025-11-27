#!/bin/bash
# Description: Trigger high CPU usage in the ad service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

# Flag name
FLAG_NAME="adHighCpu"

echo "🔥 Triggering high CPU incident in ad service..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • Ad service CPU usage will spike to 80-100%"
echo "  • Response times will increase"
echo "  • Frontend may experience timeouts calling ad service"
echo ""
echo "Monitor:"
echo "  • Prometheus: rate(process_cpu_seconds_total{service_name=\"ad\"}[1m])"
echo "  • Docker: docker stats ad"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

