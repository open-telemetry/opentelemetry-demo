#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# update-k8s.sh
#
# Purpose:
#   Updates the OpenTelemetry Demo and New Relic K8s Helm chart versions,
#   and generates their Kubernetes manifests for deployment.
#   Should be run after syncing with the latest upstream changes.
#
# How to run:
#   ./update-k8s.sh
#   (Run from the newrelic/scripts directory)
#
# Dependencies:
#   - helm
#   - yq (YAML processor)
#   - Access to the project source and Helm values files
# -----------------------------------------------------------------------------
set -euo pipefail

source "$(dirname "$0")/common.sh"

check_tool_installed helm
check_tool_installed yq

template_chart() {
    local release="$1"
    local chart="$2"
    local version="$3"
    local namespace="$4"
    local values="$5"
    local output="$6"
    helm template "$release" "$chart" --version "$version" -n "$namespace" --create-namespace -f "$values" > "$output"
}

update_version_in_script() {
    local var_name="$1"
    local version="$2"
    local script="$3"
    if [ -f "$script" ]; then
        sed -i '' "s/^$var_name=.*/$var_name=\"$version\"/" "$script"
        echo "Updated $var_name in $script to $version"
    fi
}

ensure_helm_repo "newrelic" "https://helm-charts.newrelic.com"
ensure_helm_repo "open-telemetry" "https://open-telemetry.github.io/opentelemetry-helm-charts"

check_file_exists "$OTEL_DEMO_VALUES_PATH"
check_file_exists "$NR_K8S_VALUES_PATH"

LATEST_OTEL_DEMO_CHART_VERSION=$(helm search repo open-telemetry/opentelemetry-demo --versions | awk 'NR==2 {print $2}')
echo "Latest OpenTelemetry Demo chart version: $LATEST_OTEL_DEMO_CHART_VERSION"
template_chart "otel-demo" "open-telemetry/opentelemetry-demo" "$LATEST_OTEL_DEMO_CHART_VERSION" "opentelemetry-demo" "$OTEL_DEMO_VALUES_PATH" "$OTEL_DEMO_RENDER_PATH"
update_version_in_script "OTEL_DEMO_CHART_VERSION" "$LATEST_OTEL_DEMO_CHART_VERSION" "$COMMON_SCRIPT_PATH"
echo "Completed updating the OpenTelemetry Demo app!"

LATEST_NR_K8S_CHART_VERSION=$(helm search repo newrelic/nr-k8s-otel-collector --versions | awk 'NR==2 {print $2}')
echo "Latest New Relic K8s chart version: $LATEST_NR_K8S_CHART_VERSION"
template_chart "nr-k8s-otel-collector" "newrelic/nr-k8s-otel-collector" "$LATEST_NR_K8S_CHART_VERSION" "opentelemetry-demo" "$NR_K8S_VALUES_PATH" "$NR_K8S_RENDER_PATH"
update_version_in_script "NR_K8S_CHART_VERSION" "$LATEST_NR_K8S_CHART_VERSION" "$COMMON_SCRIPT_PATH"
echo "Completed updating the New Relic K8s instrumentation!"

echo "Completed chart versions!"
