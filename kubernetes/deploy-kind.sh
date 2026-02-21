#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Deploy OpenTelemetry Demo to a local Kind cluster
#
# This script:
# 1. Creates a Kind cluster (if it doesn't exist)
# 2. Installs the Helm chart with info() function support
# 3. Deploys custom Grafana dashboards
#
# Prerequisites:
#   - kind: https://kind.sigs.k8s.io/docs/user/quick-start/#installation
#   - kubectl
#   - helm

set -e

CLUSTER_NAME="${CLUSTER_NAME:-otel-demo}"
NAMESPACE="${NAMESPACE:-otel-demo}"
RELEASE_NAME="${RELEASE_NAME:-opentelemetry-demo}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== OpenTelemetry Demo on Kind ==="
echo "Cluster: $CLUSTER_NAME"
echo "Namespace: $NAMESPACE"
echo ""

# Check prerequisites
command -v kind >/dev/null 2>&1 || { echo "Error: kind is not installed. See https://kind.sigs.k8s.io/docs/user/quick-start/#installation"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "Error: kubectl is not installed."; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "Error: helm is not installed."; exit 1; }

# Create Kind cluster if it doesn't exist
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Creating Kind cluster '$CLUSTER_NAME'..."
    kind create cluster --config "$SCRIPT_DIR/kind-config.yaml" --name "$CLUSTER_NAME"
    echo ""
else
    echo "Kind cluster '$CLUSTER_NAME' already exists."
    # Ensure kubectl context is set to the Kind cluster
    kubectl config use-context "kind-${CLUSTER_NAME}"
    echo ""
fi

# Add Helm repo
echo "Adding Helm repository..."
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts 2>/dev/null || true
helm repo update

# Create namespace
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Install/upgrade the Helm chart
echo ""
echo "Installing OpenTelemetry Demo (this may take a few minutes)..."
helm upgrade --install "$RELEASE_NAME" open-telemetry/opentelemetry-demo \
  --namespace "$NAMESPACE" \
  -f "$SCRIPT_DIR/values-info-function.yaml" \
  -f "$SCRIPT_DIR/values-kind.yaml" \
  --timeout 10m \
  --wait

# Deploy custom dashboards
echo ""
echo "Deploying custom Grafana dashboards..."

# Delete conflicting dashboards from Helm chart that don't use info() function.
# The Helm chart bundles dashboards that query metrics directly with resource
# attributes as labels. Our custom dashboards use the info() function instead.
echo "  - Removing default Helm chart dashboards..."
kubectl delete configmap grafana-dashboard-apm-dashboard --namespace "$NAMESPACE" 2>/dev/null || true
kubectl delete configmap grafana-dashboard-postgresql-dashboard --namespace "$NAMESPACE" 2>/dev/null || true

echo "  - APM Dashboard"
kubectl create configmap apm-dashboard \
  --from-file=apm-dashboard.json="$REPO_ROOT/src/grafana/provisioning/dashboards/demo/apm-dashboard.json" \
  --namespace "$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl label configmap apm-dashboard grafana_dashboard=1 --namespace "$NAMESPACE" --overwrite

echo "  - PostgreSQL Dashboard"
kubectl create configmap postgresql-dashboard \
  --from-file=postgresql-dashboard.json="$REPO_ROOT/src/grafana/provisioning/dashboards/demo/postgresql-dashboard.json" \
  --namespace "$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl label configmap postgresql-dashboard grafana_dashboard=1 --namespace "$NAMESPACE" --overwrite

# Restart Grafana to pick up dashboards
echo ""
echo "Restarting Grafana to load dashboards..."
kubectl rollout restart deployment/grafana --namespace "$NAMESPACE" 2>/dev/null || true

# Wait for pods
echo ""
echo "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance="$RELEASE_NAME" \
  --namespace "$NAMESPACE" --timeout=5m 2>/dev/null || true

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Access the demo:"
echo "  Frontend: http://localhost:8080 (via Kind NodePort)"
echo ""
echo "For Grafana, Prometheus, Jaeger use port-forward:"
echo "  kubectl port-forward svc/grafana 3000:80 -n $NAMESPACE"
echo "  kubectl port-forward svc/prometheus 9090:9090 -n $NAMESPACE"
echo "  kubectl port-forward svc/jaeger 16686:16686 -n $NAMESPACE"
echo ""
echo "View pods:"
echo "  kubectl get pods -n $NAMESPACE"
echo ""
echo "Delete cluster when done:"
echo "  kind delete cluster --name $CLUSTER_NAME"
