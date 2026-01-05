#!/bin/bash
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
#
# Deploy OpenTelemetry Demo to Azure Kubernetes Service
#
# Usage:
#   ./scripts/deploy-to-aks.sh [options]
#
# Options:
#   --resource-group, -g    Azure resource group name
#   --cluster-name, -c      AKS cluster name
#   --namespace, -n         Kubernetes namespace (default: otel-demo)
#   --skip-terraform        Skip Terraform and use existing secrets
#   --help, -h              Show this help message

set -euo pipefail

# Default values
NAMESPACE="otel-demo"
SKIP_TERRAFORM=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    head -20 "$0" | grep -E "^#" | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -c|--cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --skip-terraform)
            SKIP_TERRAFORM=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            ;;
    esac
done

# Validate required arguments if not using Terraform
if [[ "$SKIP_TERRAFORM" == "true" ]]; then
    if [[ -z "${RESOURCE_GROUP:-}" ]] || [[ -z "${CLUSTER_NAME:-}" ]]; then
        log_error "Resource group and cluster name are required when skipping Terraform"
        show_help
    fi
fi

log_info "Starting OpenTelemetry Demo deployment to AKS..."

# Step 1: Check prerequisites
log_info "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

if ! command -v az &> /dev/null; then
    log_error "Azure CLI is not installed. Please install az cli first."
    exit 1
fi

# Step 2: Get Terraform outputs or use provided values
if [[ "$SKIP_TERRAFORM" == "false" ]]; then
    log_info "Getting configuration from Terraform..."

    if [[ ! -d "$ROOT_DIR/terraform" ]]; then
        log_error "Terraform directory not found. Run 'terraform apply' first or use --skip-terraform."
        exit 1
    fi

    cd "$ROOT_DIR/terraform"

    if [[ ! -f "terraform.tfstate" ]]; then
        log_error "Terraform state not found. Run 'terraform apply' first."
        exit 1
    fi

    RESOURCE_GROUP=$(terraform output -raw resource_group_name 2>/dev/null || echo "")
    CLUSTER_NAME=$(terraform output -raw aks_cluster_name 2>/dev/null || echo "")

    if [[ -z "$RESOURCE_GROUP" ]] || [[ -z "$CLUSTER_NAME" ]]; then
        log_error "Could not get Terraform outputs. Ensure terraform apply was successful."
        exit 1
    fi

    cd "$ROOT_DIR"
fi

log_info "Resource Group: $RESOURCE_GROUP"
log_info "AKS Cluster: $CLUSTER_NAME"
log_info "Namespace: $NAMESPACE"

# Step 3: Get AKS credentials
log_info "Getting AKS credentials..."
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" --overwrite-existing

# Step 4: Create namespace
log_info "Creating namespace '$NAMESPACE'..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Step 5: Apply secrets
log_info "Applying ADX credentials..."

if [[ -f "$ROOT_DIR/kubernetes/azure/secrets.yaml" ]]; then
    kubectl apply -f "$ROOT_DIR/kubernetes/azure/secrets.yaml"
else
    log_warn "secrets.yaml not found. If using Terraform, run 'terraform apply' to generate it."
    log_warn "Otherwise, copy secrets-template.yaml to secrets.yaml and fill in your values."

    if [[ -f "$ROOT_DIR/kubernetes/azure/secrets-template.yaml" ]]; then
        log_info "Found secrets-template.yaml. Please configure it manually."
    fi
fi

# Step 6: Apply OTel Collector ConfigMap
log_info "Applying OTel Collector configuration..."
kubectl apply -f "$ROOT_DIR/kubernetes/azure/otel-collector-configmap.yaml"

# Step 7: Deploy the demo
log_info "Deploying OpenTelemetry Demo..."

if [[ -f "$ROOT_DIR/kubernetes/opentelemetry-demo-azure.yaml" ]]; then
    kubectl apply -f "$ROOT_DIR/kubernetes/opentelemetry-demo-azure.yaml"
else
    log_warn "Azure-specific manifest not found. Using base manifest..."
    log_warn "Note: This will deploy with original backends (Jaeger, Prometheus, OpenSearch)"
    kubectl apply -f "$ROOT_DIR/kubernetes/opentelemetry-demo.yaml"
fi

# Step 8: Wait for pods to be ready
log_info "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=opentelemetry-demo -n "$NAMESPACE" --timeout=300s || {
    log_warn "Some pods may not be ready yet. Check status with: kubectl get pods -n $NAMESPACE"
}

# Step 9: Show deployment status
log_info "Deployment status:"
kubectl get pods -n "$NAMESPACE"

# Step 10: Show access instructions
echo ""
log_info "Deployment complete!"
echo ""
echo "To access the services, run:"
echo ""
echo "  # Frontend (Web UI)"
echo "  kubectl port-forward -n $NAMESPACE svc/frontend-proxy 8080:8080"
echo "  Open: http://localhost:8080"
echo ""
echo "  # Grafana (Dashboards)"
echo "  kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
echo "  Open: http://localhost:3000"
echo ""
echo "  # Load Generator (Locust)"
echo "  kubectl port-forward -n $NAMESPACE svc/load-generator 8089:8089"
echo "  Open: http://localhost:8089"
echo ""
echo "To check pod status:"
echo "  kubectl get pods -n $NAMESPACE"
echo ""
echo "To view logs:"
echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/component=collector -f"
echo ""
