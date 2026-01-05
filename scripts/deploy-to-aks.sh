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
#   --use-kubectl           Use kubectl instead of Helm (legacy mode)
#   --help, -h              Show this help message

set -euo pipefail

# Default values
NAMESPACE="otel-demo"
SKIP_TERRAFORM=false
USE_KUBECTL=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
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
        --use-kubectl)
            USE_KUBECTL=true
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

echo ""
echo "=============================================================================="
echo "  OpenTelemetry Demo - Azure Data Explorer Deployment"
echo "=============================================================================="
echo ""

# Step 1: Check prerequisites
log_step "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi
log_info "kubectl: OK"

if ! command -v az &> /dev/null; then
    log_error "Azure CLI is not installed. Please install az cli first."
    exit 1
fi
log_info "az cli: OK"

if [[ "$USE_KUBECTL" == "false" ]]; then
    if ! command -v helm &> /dev/null; then
        log_warn "Helm is not installed. Falling back to kubectl mode."
        USE_KUBECTL=true
    else
        log_info "helm: OK"
    fi
fi

# Step 2: Get Terraform outputs or use provided values
if [[ "$SKIP_TERRAFORM" == "false" ]]; then
    log_step "Getting configuration from Terraform..."

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
    ADX_CLUSTER_URI=$(terraform output -raw adx_cluster_uri 2>/dev/null || echo "")

    if [[ -z "$RESOURCE_GROUP" ]] || [[ -z "$CLUSTER_NAME" ]]; then
        log_error "Could not get Terraform outputs. Ensure terraform apply was successful."
        exit 1
    fi

    cd "$ROOT_DIR"
fi

log_info "Resource Group: $RESOURCE_GROUP"
log_info "AKS Cluster: $CLUSTER_NAME"
log_info "Namespace: $NAMESPACE"
if [[ -n "${ADX_CLUSTER_URI:-}" ]]; then
    log_info "ADX Cluster: $ADX_CLUSTER_URI"
fi

# Step 3: Get AKS credentials
log_step "Getting AKS credentials..."
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" --overwrite-existing

# Step 4: Deploy based on method
if [[ "$USE_KUBECTL" == "true" ]]; then
    # Legacy kubectl deployment
    log_step "Deploying with kubectl (legacy mode)..."

    # Create namespace
    log_info "Creating namespace '$NAMESPACE'..."
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # Apply secrets
    log_info "Applying ADX credentials..."
    if [[ -f "$ROOT_DIR/kubernetes/azure/secrets.yaml" ]]; then
        kubectl apply -f "$ROOT_DIR/kubernetes/azure/secrets.yaml"
    else
        log_error "secrets.yaml not found. Run 'terraform apply' to generate it."
        exit 1
    fi

    # Apply OTel Collector ConfigMap
    log_info "Applying OTel Collector configuration..."
    if [[ -f "$ROOT_DIR/kubernetes/azure/otel-collector-configmap.yaml" ]]; then
        kubectl apply -f "$ROOT_DIR/kubernetes/azure/otel-collector-configmap.yaml"
    fi

    # Deploy the demo
    log_info "Deploying OpenTelemetry Demo..."
    if [[ -f "$ROOT_DIR/kubernetes/opentelemetry-demo.yaml" ]]; then
        kubectl apply -f "$ROOT_DIR/kubernetes/opentelemetry-demo.yaml"
    else
        log_error "Demo manifest not found."
        exit 1
    fi

else
    # Helm deployment (recommended)
    log_step "Deploying with Helm..."

    HELM_CHART_DIR="$ROOT_DIR/kubernetes/opentelemetry-demo-chart"
    VALUES_FILE="$HELM_CHART_DIR/values-generated.yaml"

    # Check if Terraform-generated values exist
    if [[ -f "$VALUES_FILE" ]]; then
        log_info "Using Terraform-generated values: values-generated.yaml"

        # Check if release exists
        if helm status otel-demo -n "$NAMESPACE" &> /dev/null; then
            log_info "Upgrading existing Helm release..."
            helm upgrade otel-demo "$HELM_CHART_DIR" \
                -f "$VALUES_FILE" \
                -n "$NAMESPACE" \
                --wait \
                --timeout 10m
        else
            log_info "Installing new Helm release..."
            helm install otel-demo "$HELM_CHART_DIR" \
                -f "$VALUES_FILE" \
                -n "$NAMESPACE" \
                --create-namespace \
                --wait \
                --timeout 10m
        fi
    else
        log_warn "Terraform-generated values not found."
        log_info "Using default values with existing secret..."

        # Check if secrets exist
        if [[ -f "$ROOT_DIR/kubernetes/azure/secrets.yaml" ]]; then
            kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
            kubectl apply -f "$ROOT_DIR/kubernetes/azure/secrets.yaml"

            if helm status otel-demo -n "$NAMESPACE" &> /dev/null; then
                helm upgrade otel-demo "$HELM_CHART_DIR" \
                    -f "$HELM_CHART_DIR/values-azure.yaml" \
                    --set azure.existingSecret=adx-credentials \
                    --set adx.clusterUri="${ADX_CLUSTER_URI:-}" \
                    -n "$NAMESPACE" \
                    --wait \
                    --timeout 10m
            else
                helm install otel-demo "$HELM_CHART_DIR" \
                    -f "$HELM_CHART_DIR/values-azure.yaml" \
                    --set azure.existingSecret=adx-credentials \
                    --set adx.clusterUri="${ADX_CLUSTER_URI:-}" \
                    -n "$NAMESPACE" \
                    --create-namespace \
                    --wait \
                    --timeout 10m
            fi
        else
            log_error "No credentials found. Run 'terraform apply' first."
            exit 1
        fi
    fi
fi

# Step 5: Wait for pods to be ready
log_step "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=opentelemetry-demo -n "$NAMESPACE" --timeout=300s 2>/dev/null || {
    log_warn "Some pods may not be ready yet. Check status with: kubectl get pods -n $NAMESPACE"
}

# Step 6: Show deployment status
log_step "Deployment status:"
echo ""
kubectl get pods -n "$NAMESPACE" --sort-by='.metadata.name'

# Step 7: Show access instructions
echo ""
echo "=============================================================================="
echo "  Deployment Complete!"
echo "=============================================================================="
echo ""
echo "To access the services, run these commands in separate terminals:"
echo ""
echo "  # Frontend (Web UI)"
echo "  kubectl port-forward -n $NAMESPACE svc/frontend-proxy 8080:8080"
echo "  Open: http://localhost:8080"
echo ""
echo "  # Grafana (Dashboards with ADX)"
echo "  kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
echo "  Open: http://localhost:3000 (admin/admin)"
echo ""
echo "  # Load Generator (Locust)"
echo "  kubectl port-forward -n $NAMESPACE svc/load-generator 8089:8089"
echo "  Open: http://localhost:8089"
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=opentelemetry-collector -f"
echo "  helm status otel-demo -n $NAMESPACE"
echo ""
