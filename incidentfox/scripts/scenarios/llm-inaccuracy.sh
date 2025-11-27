#!/bin/bash
# Description: Trigger LLM inaccurate responses

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="llmInaccurateResponse"

echo "🤖 Triggering LLM inaccurate responses..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • LLM will return inaccurate product summary for product L9ECAV7KIM"
echo "  • Data quality issue (no performance impact)"
echo "  • May affect user trust"
echo ""
echo "Monitor:"
echo "  • Check product page for product L9ECAV7KIM"
echo "  • Logs: docker compose logs product-reviews"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

