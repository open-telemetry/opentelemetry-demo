#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# validate-k8s.sh
#
# Purpose:
#   Validate the OpenTelemetry Demo using the rendered OpenTelemetry and New
#   Relic K8s Helm charts.
#
# How to run:
#   ./validate-k8s.sh
#   (Run from the newrelic/scripts directory)
#
# Environment variables:
#   NEW_RELIC_LICENSE_KEY   Your New Relic license key (will prompt if not set)
#                           (used by install-k8s.sh)
#   IS_OPENSHIFT_CLUSTER    Set to 'y' if deploying to OpenShift cluster or
#                           'n' for standard Kubernetes cluster
#                           (will prompt if not set)
#                           (used by install-k8s.sh)
#   NEW_RELIC_API_KEY       Your New Relic User API key (will prompt if not set)
#                           (used by validate-newrelic.sh)
#   NEW_RELIC_ACCOUNT_ID    Your New Relic Account ID (will prompt if not set)
#                           (used by validate-newrelic.sh)
#
# Dependencies:
#   - kubectl (used by install-k8s.sh, validate-ui.sh, and cleanup-k8s.sh)
#   - helm (used by install-k8s.sh and cleanup-k8s.sh)
#   - pip (used by validate-ui.sh)
#   - python3 (used by validate-ui.sh and validate-newrelic.sh)
#   - Access to the target Kubernetes cluster
# -----------------------------------------------------------------------------
set -euo pipefail

# Source the common functions and variables
source "$(dirname "$0")/common.sh"

# Make sure tools required by all scripts are installed
check_tool_installed kubectl
check_tool_installed helm
check_tool_installed pip
check_tool_installed python3

# Load environment variables from .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
  source "$SCRIPT_DIR/.env"
fi

# Ensure environment variables required for all scripts are set, prompting
# the user if necessary
prompt_for_license_key
prompt_for_openshift
prompt_for_api_key
prompt_for_account_id

# Run the install script
echo "Installing OpenTelemetry Demo and New Relic Collector Kubernetes resources..."
NEW_RELIC_LICENSE_KEY="$NEW_RELIC_LICENSE_KEY" \
  IS_OPENSHIFT_CLUSTER="$IS_OPENSHIFT_CLUSTER" \
  $SCRIPT_DIR/install-k8s.sh

# Begin validation
echo "Validating OpenTelemetry Demo and New Relic Collector Kubernetes installation..."

# Wait up to 5 minutes for all pods to be in Running state
echo "Waiting for all pods to be in Running state..."
kubectl wait --for=jsonpath='{.status.phase}'=Running pod --all \
  -n opentelemetry-demo --timeout=300s
echo "All pods are in Running state!"

# Maybe run the UI validation script
if [ "${UI_VALIDATION_ENABLED:-false}" = "true" ]; then
  echo "Running UI validation script..."
  EXIT_CODE=0
  $SCRIPT_DIR/validate-ui.sh k8s || EXIT_CODE=$?

  if [ $EXIT_CODE -ne 0 ]; then
    # Selenium scripts can be finnicky so we retry once if it fails
    echo "UI validation failed on first attempt: Retrying UI validation script..."
    EXIT_CODE=0
    $SCRIPT_DIR/validate-ui.sh k8s || EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
      echo "UI validation failed: Issues detected in OpenTelemetry Demo UI validation after two attempts."
      echo "Try running ./validate-k8s.sh again or run ./validate-ui.sh to manually run the UI validation."
      exit 1
    fi
  fi
fi

# Pause briefly to allow data to propagate to New Relic
echo "Pausing to allow data to propagate to New Relic..."
sleep 30

# Run the New Relic validation script
echo "Running New Relic validation script..."
EXIT_CODE=0
NEW_RELIC_API_KEY="$NEW_RELIC_API_KEY" \
  NEW_RELIC_ACCOUNT_ID="$NEW_RELIC_ACCOUNT_ID" \
  $SCRIPT_DIR/validate-newrelic.sh || EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "New Relic validation failed: Issues detected in OpenTelemetry Demo New Relic validation."
  echo "Try running ./validate-k8s.sh again or run ./validate-newrelic.sh to manually run the New Relic validation."
  exit 1
fi

# Validation succeeded, maybe cleanup K8s resources
if [ "${K8S_CLEANUP_ENABLED:-true}" = "true" ]; then
  echo "Validation succeeded! Cleaning up Kubernetes resources..."
  $SCRIPT_DIR/cleanup-k8s.sh
fi
