#!/usr/bin/env bash
set -euo pipefail
# Purpose: Updates de OpenTelemetry Demo Helm chart and generates the Kubernetes manifests.
# Notes:
#   This should be run after the OpenTelemetry Demo has been synced with the latest changes from the upstream repository.
# Requirements:
#   - yq: A portable command-line YAML processor.
#   Both can be installed using brew:
#       brew install yq
#
# Example Usage:
#   ./update-k8s.sh

# Set default paths if environment variables are not set
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
NR_HELM_VALUES_PATH=${NR_HELM_VALUES_PATH:-"$SCRIPT_DIR/../k8s/helm/values.yaml"}
NR_HELM_TEMPLATE_DEST=${NR_HELM_TEMPLATE_DEST:-"$SCRIPT_DIR/../k8s/rendered/manifest.yaml"}
INSTALL_K8S_SH="$SCRIPT_DIR/install-k8s.sh"

# Get the latest chart version from the repo
LATEST_OTEL_DEMO_CHART_VERSION=$(helm search repo open-telemetry/opentelemetry-demo --versions | awk 'NR==2 {print $2}')

echo "Latest OpenTelemetry Demo chart version: $LATEST_OTEL_DEMO_CHART_VERSION"

# Delete any older versions of the New Relic helm template manifests
[ -e "$NR_HELM_TEMPLATE_DEST" ] && rm "$NR_HELM_TEMPLATE_DEST"

# Template the chart using the latest version
helm template otel-demo open-telemetry/opentelemetry-demo --version "$LATEST_OTEL_DEMO_CHART_VERSION" -n opentelemetry-demo --create-namespace -f "$NR_HELM_VALUES_PATH" > "$NR_HELM_TEMPLATE_DEST"

# Update the OTEL_DEMO_CHART_VERSION variable in install-k8s.sh
if [ -f "$INSTALL_K8S_SH" ]; then
    sed -i '' "s/^OTEL_DEMO_CHART_VERSION=.*/OTEL_DEMO_CHART_VERSION=\"$LATEST_OTEL_DEMO_CHART_VERSION\"/" "$INSTALL_K8S_SH"
    echo "Updated OTEL_DEMO_CHART_VERSION in $INSTALL_K8S_SH to $LATEST_OTEL_DEMO_CHART_VERSION"
fi

echo "Completed updating the ./k8s/rendered/manifest.yaml for the OpenTelemetry demo app!"