#!/bin/bash
# -----------------------------------------------------------------------------
# cleanup-k8s.sh
#
# Purpose:
#   Uninstalls the OpenTelemetry Demo and New Relic Kubernetes instrumentation
#   from a cluster by removing Helm releases and deleting the namespace.
#
# How to run:
#   ./cleanup-k8s.sh
#   (Run from the newrelic/scripts directory)
#
# Dependencies:
#   - kubectl
#   - helm
#   - Access to the target Kubernetes cluster
# -----------------------------------------------------------------------------
set -euo pipefail

source "$(dirname "$0")/common.sh"

check_tool_installed helm
check_tool_installed kubectl

cleanup_helm_release() {
    local release=$1
    local namespace=$2
    if helm status "$release" -n "$namespace" &> /dev/null; then
        echo "Helm release '$release' found. Uninstalling..."
        helm uninstall "$release" -n "$namespace"
    fi
}

cleanup_namespace() {
    local namespace=$1
    if kubectl get namespace "$namespace" &> /dev/null; then
        echo "Namespace '$namespace' found. Deleting..."
        kubectl delete namespace "$namespace"
    fi
}

cleanup_helm_release "$OTEL_DEMO_RELEASE_NAME" "$OTEL_DEMO_NAMESPACE"
cleanup_helm_release "$NR_K8S_RELEASE_NAME" "$OTEL_DEMO_NAMESPACE"
cleanup_namespace "$OTEL_DEMO_NAMESPACE"

echo "Cleanup completed successfully."

exit 0
