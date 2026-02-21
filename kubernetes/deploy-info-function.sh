#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Deploy OpenTelemetry Demo with experimental Prometheus info() function support
#
# This script:
# 1. Installs/upgrades the Helm chart with custom values
# 2. Deploys custom Grafana dashboards that use the info() function

set -e

NAMESPACE="${NAMESPACE:-otel-demo}"
RELEASE_NAME="${RELEASE_NAME:-opentelemetry-demo}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Deploying OpenTelemetry Demo with info() function support ==="
echo "Namespace: $NAMESPACE"
echo "Release: $RELEASE_NAME"
echo ""

# Add Helm repo if not already added
echo "Adding Helm repository..."
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts 2>/dev/null || true
helm repo update

# Create namespace if it doesn't exist
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Install/upgrade the Helm chart
echo ""
echo "Installing/upgrading Helm chart..."
helm upgrade --install "$RELEASE_NAME" open-telemetry/opentelemetry-demo \
  --namespace "$NAMESPACE" \
  -f "$SCRIPT_DIR/values-info-function.yaml" \
  --wait

# Deploy custom dashboards as ConfigMaps
echo ""
echo "Deploying custom Grafana dashboards..."

# APM Dashboard
echo "  - APM Dashboard"
kubectl create configmap apm-dashboard \
  --from-file=apm-dashboard.json="$REPO_ROOT/src/grafana/provisioning/dashboards/demo/apm-dashboard.json" \
  --namespace "$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl label configmap apm-dashboard grafana_dashboard=1 --namespace "$NAMESPACE" --overwrite

# PostgreSQL Dashboard
echo "  - PostgreSQL Dashboard"
kubectl create configmap postgresql-dashboard \
  --from-file=postgresql-dashboard.json="$REPO_ROOT/src/grafana/provisioning/dashboards/demo/postgresql-dashboard.json" \
  --namespace "$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl label configmap postgresql-dashboard grafana_dashboard=1 --namespace "$NAMESPACE" --overwrite

# Restart Grafana to pick up the new dashboards
echo ""
echo "Restarting Grafana to load dashboards..."
kubectl rollout restart deployment/grafana --namespace "$NAMESPACE" 2>/dev/null || \
kubectl rollout restart deployment/"$RELEASE_NAME"-grafana --namespace "$NAMESPACE" 2>/dev/null || \
echo "  (Could not restart Grafana - dashboards will load on next restart)"

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Access the demo:"
echo "  kubectl port-forward svc/frontend-proxy 8080:8080 -n $NAMESPACE"
echo "  Open http://localhost:8080"
echo ""
echo "Access Grafana:"
echo "  kubectl port-forward svc/grafana 3000:80 -n $NAMESPACE"
echo "  Open http://localhost:3000 (admin/admin)"
