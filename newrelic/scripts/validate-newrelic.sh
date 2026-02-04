#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# validate-newrelic.sh
#
# Purpose:
#   Validate the OpenTelemetry Demo is sending the expected data to New Relic.
#
# How to run:
#   ./validate-newrelic.sh
#   (Run from the newrelic/scripts directory)
#
# Environment variables:
#   NEW_RELIC_API_KEY       Your New Relic User API key (will prompt if not set)
#   NEW_RELIC_ACCOUNT_ID    Your New Relic Account ID (will prompt if not set)
#
# Dependencies:
#   - python3
# -----------------------------------------------------------------------------
set -euo pipefail

# Source the common functions and variables
source "$(dirname "$0")/common.sh"

# Make sure required tools are installed
check_tool_installed python3

# Load environment variables from .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
  source "$SCRIPT_DIR/.env"
fi

# Ensure New Relic API key and account ID are set, prompting the user if
# necessary
prompt_for_api_key
prompt_for_account_id

# Run the validation script to check data in New Relic
echo "Running New Relic validation script..."
EXIT_CODE=0
NEW_RELIC_API_KEY="$NEW_RELIC_API_KEY" \
  NEW_RELIC_ACCOUNT_ID="$NEW_RELIC_ACCOUNT_ID" \
  python3 "$SCRIPT_DIR/test_otel_demo_newrelic.py" || EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "OpenTelemetry Demo New Relic validation failed."
  exit 1
fi

echo "OpenTelemetry Demo New Relic validation succeeded!"
