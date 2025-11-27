#!/bin/bash
# Description: Trigger LLM rate limit errors

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

FLAG_NAME="llmRateLimitError"

echo "⏱️  Triggering LLM rate limit errors..."

# Backup the config
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"

# Enable the flag
jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

echo "✓ Flag '${FLAG_NAME}' set to 'on'"
echo ""
echo "Expected behavior:"
echo "  • LLM service will intermittently return rate limit errors"
echo "  • Some product reviews will fail to load summaries"
echo "  • System will fall back to cached summaries when available"
echo "  • Logs will show 'rate limit exceeded' errors"
echo ""
echo "Monitor:"
echo "  • Logs: docker compose logs product-reviews | grep -i 'rate limit'"
echo "  • Check product pages for missing reviews"
echo ""
echo "To disable: ./trigger-incident.sh clear-all"

