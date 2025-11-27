#!/bin/bash
# Description: Trigger product catalog failures

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="productCatalogFailure"

echo "📚 Triggering product catalog failure..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • Product catalog will fail for specific products"
echo "  • Product pages will show errors"
echo "  • Search results may be incomplete"
echo "  • Recommendations may fail"
echo "  • Cart operations may fail"
echo ""
echo "Monitor:"
echo "  • Errors: rate(http_server_requests_total{service_name=\"product-catalog\",http_status_code=~\"5..\"}[5m])"
echo "  • Logs: docker compose logs product-catalog | grep ERROR"
echo "  • Traces: http://localhost:16686/search?service=product-catalog&tags={\"error\":\"true\"}"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

