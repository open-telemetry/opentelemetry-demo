#!/bin/bash
# Description: Trigger GC pressure in ad service (Java)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="adManualGc"

echo "♻️  Triggering GC pressure in ad service..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • Frequent full GC pauses in ad service"
echo "  • Intermittent latency spikes (during GC)"
echo "  • Request queueing"
echo "  • Possible timeout errors"
echo "  • Sawtooth memory pattern"
echo ""
echo "Monitor:"
echo "  • GC time: rate(jvm_gc_pause_seconds_sum{service_name=\"ad\"}[5m])"
echo "  • GC frequency: rate(jvm_gc_pause_seconds_count{service_name=\"ad\"}[1m])"
echo "  • Memory: jvm_memory_used_bytes{service_name=\"ad\"}"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

