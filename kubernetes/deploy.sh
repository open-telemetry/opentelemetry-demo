#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Deploy OpenTelemetry Demo to a Kubernetes cluster
#
# This script:
# 1. Installs/upgrades the Helm chart with info() function values
# 2. Deploys custom Grafana dashboards that use the info() function
#
# Usage:
#   kubernetes/deploy.sh --context kind-otel-demo
#   kubernetes/deploy.sh --context kind-otel-demo -f kubernetes/values-kind.yaml
#
# The --context argument is required and passed to both kubectl and helm.
# All other arguments are passed to helm upgrade.
#
# Environment variables:
#   NAMESPACE     - Kubernetes namespace (default: otel-demo)
#   RELEASE_NAME  - Helm release name (default: opentelemetry-demo)

set -e

NAMESPACE="${NAMESPACE:-otel-demo}"
RELEASE_NAME="${RELEASE_NAME:-opentelemetry-demo}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse --context argument
KUBE_CONTEXT=""
HELM_ARGS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --context)
      KUBE_CONTEXT="$2"
      shift 2
      ;;
    *)
      HELM_ARGS="$HELM_ARGS $1"
      shift
      ;;
  esac
done

if [ -z "$KUBE_CONTEXT" ]; then
  echo "Error: --context is required"
  echo "Usage: $0 --context <kube-context> [helm args...]"
  exit 1
fi

KUBECTL="kubectl --context $KUBE_CONTEXT"
HELM_CONTEXT="--kube-context $KUBE_CONTEXT"

echo "=== Deploying OpenTelemetry Demo ==="
echo "Namespace: $NAMESPACE"
echo "Release: $RELEASE_NAME"
echo "Context: $KUBE_CONTEXT"
echo ""

# Add Helm repo if not already added
echo "Adding Helm repository..."
helm repo add --force-update open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts

# Create namespace if it doesn't exist
$KUBECTL create namespace "$NAMESPACE" --dry-run=client -o yaml | $KUBECTL apply -f -

# Install/upgrade the Helm chart
echo ""
echo "Installing/upgrading Helm chart..."
# shellcheck disable=SC2086
helm upgrade --install "$RELEASE_NAME" open-telemetry/opentelemetry-demo \
  $HELM_CONTEXT \
  --namespace "$NAMESPACE" \
  -f "$SCRIPT_DIR/values.yaml" \
  $HELM_ARGS \
  --wait

# Deploy custom dashboards as ConfigMaps.
# Delete conflicting dashboards from Helm chart that don't use info() function.
echo ""
echo "Deploying custom Grafana dashboards..."
echo "  - Removing default Helm chart dashboards..."
$KUBECTL delete configmap grafana-dashboard-apm-dashboard --namespace "$NAMESPACE" --ignore-not-found
$KUBECTL delete configmap grafana-dashboard-postgresql-dashboard --namespace "$NAMESPACE" --ignore-not-found
$KUBECTL delete configmap grafana-dashboard-opentelemetry-collector --namespace "$NAMESPACE" --ignore-not-found

echo "  - APM Dashboard"
$KUBECTL create configmap apm-dashboard \
  --from-file=apm-dashboard.json="$REPO_ROOT/src/grafana/provisioning/dashboards/demo/apm-dashboard.json" \
  --namespace "$NAMESPACE" \
  --dry-run=client -o yaml | $KUBECTL apply -f -
$KUBECTL label configmap apm-dashboard grafana_dashboard=1 --namespace "$NAMESPACE" --overwrite

echo "  - PostgreSQL Dashboard"
$KUBECTL create configmap postgresql-dashboard \
  --from-file=postgresql-dashboard.json="$REPO_ROOT/src/grafana/provisioning/dashboards/demo/postgresql-dashboard.json" \
  --namespace "$NAMESPACE" \
  --dry-run=client -o yaml | $KUBECTL apply -f -
$KUBECTL label configmap postgresql-dashboard grafana_dashboard=1 --namespace "$NAMESPACE" --overwrite

echo "  - OpenTelemetry Collector Dashboard"
$KUBECTL create configmap otel-collector-dashboard \
  --from-file=opentelemetry-collector.json="$REPO_ROOT/src/grafana/provisioning/dashboards/demo/opentelemetry-collector.json" \
  --namespace "$NAMESPACE" \
  --dry-run=client -o yaml | $KUBECTL apply -f -
$KUBECTL label configmap otel-collector-dashboard grafana_dashboard=1 --namespace "$NAMESPACE" --overwrite

# Restart Grafana to pick up the new dashboards
echo ""
echo "Restarting Grafana to load dashboards..."
$KUBECTL rollout restart deployment/grafana --namespace "$NAMESPACE" 2>/dev/null || \
$KUBECTL rollout restart deployment/"$RELEASE_NAME"-grafana --namespace "$NAMESPACE" 2>/dev/null || \
echo "  (Could not restart Grafana - dashboards will load on next restart)"

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Access the demo:"
echo "  kubectl --context $KUBE_CONTEXT port-forward svc/frontend-proxy 8080:8080 -n $NAMESPACE"
echo "  Open http://localhost:8080"
echo ""
echo "Access Grafana:"
echo "  kubectl --context $KUBE_CONTEXT port-forward svc/grafana 3000:80 -n $NAMESPACE"
echo "  Open http://localhost:3000 (admin/admin)"
