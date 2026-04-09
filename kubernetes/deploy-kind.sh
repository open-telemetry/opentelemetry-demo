#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Deploy OpenTelemetry Demo to a local Kind cluster
#
# This script creates a Kind cluster and delegates the actual deployment
# to deploy.sh with Kind-specific values.
#
# Prerequisites:
#   - kind: https://kind.sigs.k8s.io/docs/user/quick-start/#installation
#   - kubectl
#   - helm

set -e

CLUSTER_NAME="${CLUSTER_NAME:-otel-demo}"
KUBE_CONTEXT="kind-${CLUSTER_NAME}"
export NAMESPACE="${NAMESPACE:-otel-demo}"
export RELEASE_NAME="${RELEASE_NAME:-opentelemetry-demo}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check prerequisites
command -v kind >/dev/null 2>&1 || { echo "Error: kind is not installed. See https://kind.sigs.k8s.io/docs/user/quick-start/#installation"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "Error: kubectl is not installed."; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "Error: helm is not installed."; exit 1; }

echo "=== OpenTelemetry Demo on Kind ==="
echo "Cluster: $CLUSTER_NAME"
echo ""

# Create Kind cluster if it doesn't exist
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Creating Kind cluster '$CLUSTER_NAME'..."
    kind create cluster --config "$SCRIPT_DIR/kind-config.yaml" --name "$CLUSTER_NAME"
    echo ""
else
    echo "Kind cluster '$CLUSTER_NAME' already exists."
    echo ""
fi

# Deploy using the shared script with Kind-specific values
"$SCRIPT_DIR/deploy.sh" \
  --context "$KUBE_CONTEXT" \
  -f "$SCRIPT_DIR/values-kind.yaml" \
  --timeout 10m

# Wait for pods
echo ""
echo "Waiting for pods to be ready..."
kubectl --context "$KUBE_CONTEXT" wait --for=condition=ready \
  pod -l app.kubernetes.io/instance="$RELEASE_NAME" \
  --namespace "$NAMESPACE" --timeout=5m 2>/dev/null || true

echo ""
echo "Access the demo:"
echo "  Frontend: http://localhost:8080 (via Kind NodePort)"
echo ""
echo "For Grafana, Prometheus, Jaeger use port-forward:"
echo "  kubectl --context $KUBE_CONTEXT port-forward svc/grafana 3000:80 -n $NAMESPACE"
echo "  kubectl --context $KUBE_CONTEXT port-forward svc/prometheus 9090:9090 -n $NAMESPACE"
echo "  kubectl --context $KUBE_CONTEXT port-forward svc/jaeger 16686:16686 -n $NAMESPACE"
echo ""
echo "View pods:"
echo "  kubectl --context $KUBE_CONTEXT get pods -n $NAMESPACE"
echo ""
echo "Delete cluster when done:"
echo "  kind delete cluster --name $CLUSTER_NAME"
