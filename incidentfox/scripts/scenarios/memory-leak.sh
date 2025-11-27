#!/bin/bash
# Description: Trigger memory leak in the email service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="emailMemoryLeak"
SEVERITY="${1:-10x}"  # Default to 10x leak rate

# Validate severity
case "$SEVERITY" in
    1x|10x|100x|1000x|10000x)
        ;;
    *)
        echo "❌ Invalid severity: $SEVERITY"
        echo "Valid options: 1x, 10x, 100x, 1000x, 10000x"
        exit 1
        ;;
esac

echo "💧 Triggering memory leak in email service (severity: ${SEVERITY})..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag with specified severity
jq ".flags.${FLAG_NAME}.defaultVariant = \"${SEVERITY}\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to '${SEVERITY}'"
echo ""
echo "Expected behavior:"
echo "  • Email service memory usage will grow steadily"
echo "  • Service may eventually be OOM killed and restart"
echo "  • Leak rate depends on severity:"
echo "    - 1x:    ~10 MB/min  (slow)"
echo "    - 10x:   ~100 MB/min (medium)"
echo "    - 100x:  ~1 GB/min   (fast)"
echo "    - 1000x: ~10 GB/min  (very fast)"
echo ""
echo "Monitor:"
echo "  • Prometheus: process_resident_memory_bytes{service_name=\"email\"}"
echo "  • Docker: docker stats email"
echo ""
echo "⚠️  Service will need restart to clear leaked memory"
echo "To disable: ./trigger-incident.sh clear-all"

