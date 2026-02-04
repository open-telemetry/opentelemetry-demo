#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# validate-ui.sh
#
# Purpose:
#   Validate the OpenTelemetry Demo UI works as expected using Selenium.
#
# How to run:
#   ./validate-ui.sh
#   (Run from the newrelic/scripts directory)
#
# Environment variables: N/a
#
# Dependencies:
#   - kubectl (if $1 = "k8s")
#   - pip
#   - python3
#   - Access to the target Kubernetes cluster
# -----------------------------------------------------------------------------
set -euo pipefail

# Source the common functions and variables
source "$(dirname "$0")/common.sh"

# Make sure required tools are installed
check_tool_installed pip
check_tool_installed python3

# Setup port forwarding if validating against Kubernetes
if [ "${1:-}" = "k8s" ]; then
  check_tool_installed kubectl

  # Function to kill the port-forward process on script exit
  function cleanup() {
      echo "Cleaning up port-forward process with PID: $PORT_FORWARD_PID"
      kill $PORT_FORWARD_PID 2>/dev/null
  }

  # Setup port forwarding for frontend-proxy
  echo "Setting up port forwarding for frontend-proxy..."
  kubectl port-forward svc/frontend-proxy -n opentelemetry-demo 8080 &

  # Capture the PID of the port-forward process and set up trap for cleanup on
  # exit
  PORT_FORWARD_PID=$!
  trap cleanup EXIT

  # Allow some time for port forwarding to establish
  echo "Waiting for port forwarding to establish..."
  sleep 5
fi

# Install selenium if not already installed
pip install selenium

# Run the validation Selenium script
echo "Running UI validation Selenium script..."
EXIT_CODE=0
python3 "$SCRIPT_DIR/test_otel_demo_ui.py" || EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "OpenTelemetry Demo UI validation failed."
  exit 1
fi

echo "OpenTelemetry Demo UI validation succeeded!"
