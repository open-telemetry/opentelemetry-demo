#!/bin/bash
# IncidentFox: Idempotent AWS deployment script
#
# This script deploys the complete OpenTelemetry Demo stack to AWS EKS:
# - VPC with public/private subnets
# - EKS cluster with managed node groups
# - AWS Secrets Manager for sensitive data
# - External Secrets Operator for k8s secret sync
# - OpenTelemetry Demo via Helm
#
# Usage: ./build-all.sh [command]
#
# Commands:
#   deploy    - Deploy/update everything (default)
#   destroy   - Tear down everything
#   status    - Show deployment status
#   kubeconfig - Update local kubeconfig

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INCIDENTFOX_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${INCIDENTFOX_ROOT}/terraform"
HELM_DIR="${INCIDENTFOX_ROOT}/helm"

# AWS Configuration (can be overridden via environment variables)
AWS_REGION="${AWS_REGION:-us-west-2}"
CLUSTER_NAME="${CLUSTER_NAME:-incidentfox-demo}"
ENVIRONMENT="${ENVIRONMENT:-lab}"
AWS_PROFILE="${AWS_PROFILE:-}"

# Wrapper so we consistently use AWS_PROFILE when provided.
aws_cli() {
    if [ -n "${AWS_PROFILE}" ]; then
        aws --profile "${AWS_PROFILE}" "$@"
    else
        aws "$@"
    fi
}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=0
    
    # Required tools
    for tool in aws terraform kubectl helm jq; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "Required tool not found: $tool"
            missing=1
        else
            log_success "Found: $tool ($(command -v $tool))"
        fi
    done
    
    # AWS credentials
    if ! aws_cli sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        log_info "If you use named profiles, set AWS_PROFILE (e.g. AWS_PROFILE=incidentfox) and login/configure."
        log_info "Examples:"
        log_info "  - Static creds: aws configure --profile incidentfox"
        log_info "  - SSO:          aws sso login --profile incidentfox"
        missing=1
    else
        local account=$(aws_cli sts get-caller-identity --query Account --output text)
        local user=$(aws_cli sts get-caller-identity --query Arn --output text)
        log_success "AWS credentials valid: $user (Account: $account)"
    fi
    
    # Terraform version check
    local tf_version=$(terraform version -json | jq -r '.terraform_version')
    log_info "Terraform version: $tf_version"
    
    if [ $missing -eq 1 ]; then
        log_error "Prerequisites check failed. Please install missing tools."
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# Deploy infrastructure with Terraform
deploy_infrastructure() {
    log_info "Deploying infrastructure with Terraform..."
    
    cd "$TERRAFORM_DIR"
    
    # Initialize Terraform (idempotent)
    log_info "Initializing Terraform..."
    terraform init -upgrade
    
    # Create terraform.tfvars if it doesn't exist
    if [ ! -f terraform.tfvars ]; then
        log_warning "terraform.tfvars not found, creating from example..."
        if [ -f terraform.tfvars.example ]; then
            cp terraform.tfvars.example terraform.tfvars
            log_info "Please review and edit terraform.tfvars before proceeding"
            exit 1
        fi
    fi
    
    # Plan
    log_info "Planning infrastructure changes..."
    terraform plan -out=tfplan
    
    # Apply (idempotent)
    log_info "Applying infrastructure changes..."
    terraform apply tfplan
    
    # Clean up plan file
    rm -f tfplan
    
    log_success "Infrastructure deployed"
    
    # Export outputs
    export VPC_ID=$(terraform output -raw vpc_id)
    export CLUSTER_NAME=$(terraform output -raw cluster_name)
    export CLUSTER_ENDPOINT=$(terraform output -raw cluster_endpoint)
    
    log_info "VPC ID: $VPC_ID"
    log_info "Cluster: $CLUSTER_NAME"
    log_info "Endpoint: $CLUSTER_ENDPOINT"
}

# Update kubeconfig
update_kubeconfig() {
    log_info "Updating kubeconfig..."
    
    aws_cli eks update-kubeconfig \
        --name "$CLUSTER_NAME" \
        --region "$AWS_REGION" \
        --alias "$CLUSTER_NAME"
    
    # Verify connection
    if kubectl cluster-info &> /dev/null; then
        log_success "Connected to cluster: $CLUSTER_NAME"
        kubectl get nodes
    else
        log_error "Failed to connect to cluster"
        exit 1
    fi
}

# Deploy External Secrets Operator
deploy_external_secrets() {
    log_info "Deploying External Secrets Operator..."
    
    # Add Helm repo
    helm repo add external-secrets https://charts.external-secrets.io
    helm repo update
    
    # Install/upgrade External Secrets Operator (idempotent)
    helm upgrade --install external-secrets \
        external-secrets/external-secrets \
        --namespace external-secrets-system \
        --create-namespace \
        --set installCRDs=true \
        --wait
    
    log_success "External Secrets Operator deployed"
    
    # Wait for operator to be ready
    log_info "Waiting for External Secrets Operator..."
    kubectl wait --for=condition=ready pod \
        -l app.kubernetes.io/name=external-secrets \
        -n external-secrets-system \
        --timeout=300s
    
    log_success "External Secrets Operator is ready"
}

# Configure secrets
configure_secrets() {
    log_info "Configuring secrets..."
    
    cd "$TERRAFORM_DIR"
    
    # Get IRSA role ARN for External Secrets
    local eso_role_arn=$(terraform output -raw external_secrets_role_arn)
    
    log_info "Creating SecretStore for AWS Secrets Manager..."
    
    # Create SecretStore (idempotent)
    kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: otel-demo
spec:
  provider:
    aws:
      service: SecretsManager
      region: ${AWS_REGION}
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
EOF
    
    log_success "SecretStore configured"
    
    # Create ExternalSecrets for demo services (idempotent)
    log_info "Creating ExternalSecret resources..."
    
    kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgres-credentials
  namespace: otel-demo
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: postgres-credentials
    creationPolicy: Owner
  data:
    - secretKey: password
      remoteRef:
        key: incidentfox-demo/postgres
        property: password
    - secretKey: username
      remoteRef:
        key: incidentfox-demo/postgres
        property: username
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: grafana-credentials
  namespace: otel-demo
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: grafana-credentials
    creationPolicy: Owner
  data:
    - secretKey: admin-password
      remoteRef:
        key: incidentfox-demo/grafana
        property: admin-password
    - secretKey: admin-user
      remoteRef:
        key: incidentfox-demo/grafana
        property: admin-user
EOF
    
    log_success "ExternalSecrets created"
    
    # Wait for secrets to sync
    log_info "Waiting for secrets to sync from AWS Secrets Manager..."
    sleep 10
    
    if kubectl get secret postgres-credentials -n otel-demo &> /dev/null; then
        log_success "Secrets synced successfully"
    else
        log_warning "Secrets not yet synced, this may take a few moments"
    fi
}

# Deploy OpenTelemetry Demo via Helm
deploy_otel_demo() {
    log_info "Deploying OpenTelemetry Demo..."
    
    cd "$HELM_DIR"
    
    # Get ALB details from Terraform
    cd "$TERRAFORM_DIR"
    local alb_dns=$(terraform output -raw alb_dns_name || echo "")
    
    cd "$HELM_DIR"
    
    # Create namespace (idempotent)
    kubectl create namespace otel-demo --dry-run=client -o yaml | kubectl apply -f -
    
    # Add OpenTelemetry Helm repo
    helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
    helm repo update
    
    # Install/upgrade OpenTelemetry Demo (idempotent)
    log_info "Installing/upgrading OpenTelemetry Demo..."
    
    helm upgrade --install otel-demo open-telemetry/opentelemetry-demo \
        --namespace otel-demo \
        --values values-aws.yaml \
        --values values-incidentfox.yaml \
        --set global.region="${AWS_REGION}" \
        --set global.environment="${ENVIRONMENT}" \
        --wait \
        --timeout 15m
    
    log_success "OpenTelemetry Demo deployed"
    
    # Wait for all pods to be ready
    log_info "Waiting for all pods to be ready..."
    kubectl wait --for=condition=ready pod \
        --all \
        -n otel-demo \
        --timeout=600s || log_warning "Some pods may still be starting"
    
    log_success "All pods are ready"
}

# Show deployment status
show_status() {
    log_info "Deployment Status"
    echo ""
    
    # Terraform state
    cd "$TERRAFORM_DIR"
    if [ -f terraform.tfstate ]; then
        log_info "Infrastructure Status:"
        echo "  VPC ID: $(terraform output -raw vpc_id 2>/dev/null || echo 'N/A')"
        echo "  Cluster: $(terraform output -raw cluster_name 2>/dev/null || echo 'N/A')"
        echo "  Endpoint: $(terraform output -raw cluster_endpoint 2>/dev/null || echo 'N/A')"
        echo ""
    else
        log_warning "No Terraform state found - infrastructure not deployed"
        echo ""
    fi
    
    # Kubernetes status
    if kubectl cluster-info &> /dev/null; then
        log_info "Kubernetes Status:"
        echo ""
        
        echo "  Nodes:"
        kubectl get nodes -o wide
        echo ""
        
        echo "  Pods in otel-demo namespace:"
        kubectl get pods -n otel-demo
        echo ""
        
        echo "  Services:"
        kubectl get svc -n otel-demo
        echo ""
        
        echo "  Ingress:"
        kubectl get ingress -n otel-demo
        echo ""
        
        # Check External Secrets
        if kubectl get namespace external-secrets-system &> /dev/null; then
            echo "  External Secrets:"
            kubectl get externalsecret -n otel-demo
            echo ""
        fi
        
        log_info "Access URLs:"
        local alb_dns=$(kubectl get ingress -n otel-demo -o json | jq -r '.items[0].status.loadBalancer.ingress[0].hostname' 2>/dev/null || echo "")
        if [ -n "$alb_dns" ] && [ "$alb_dns" != "null" ]; then
            echo "  Frontend:    http://${alb_dns}/"
            echo "  Grafana:     http://${alb_dns}/grafana"
            echo "  Jaeger:      http://${alb_dns}/jaeger/ui"
            echo "  Prometheus:  http://${alb_dns}/prometheus"
        else
            echo "  ALB not yet provisioned, use port-forward:"
            echo "    kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080"
        fi
        echo ""
    else
        log_warning "Cannot connect to Kubernetes cluster"
        echo ""
    fi
}

# Destroy everything
destroy_all() {
    log_warning "This will destroy ALL resources!"
    read -p "Are you sure? Type 'yes' to confirm: " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Destroy cancelled"
        exit 0
    fi
    
    log_info "Destroying resources..."
    
    # Delete Helm releases first
    if kubectl cluster-info &> /dev/null; then
        log_info "Deleting Helm releases..."
        helm uninstall otel-demo -n otel-demo || true
        helm uninstall external-secrets -n external-secrets-system || true
        
        log_info "Deleting namespaces..."
        kubectl delete namespace otel-demo --timeout=300s || true
        kubectl delete namespace external-secrets-system --timeout=300s || true
    fi
    
    # Destroy infrastructure
    cd "$TERRAFORM_DIR"
    if [ -f terraform.tfstate ]; then
        log_info "Destroying infrastructure with Terraform..."
        terraform destroy -auto-approve
        log_success "Infrastructure destroyed"
    else
        log_warning "No Terraform state found"
    fi
    
    log_success "All resources destroyed"
}

# Main deployment flow
deploy_all() {
    log_info "Starting deployment to AWS..."
    log_info "Region: $AWS_REGION"
    log_info "Cluster: $CLUSTER_NAME"
    log_info "Environment: $ENVIRONMENT"
    echo ""
    
    # Step 1: Prerequisites
    check_prerequisites
    echo ""
    
    # Step 2: Infrastructure
    deploy_infrastructure
    echo ""
    
    # Step 3: Kubeconfig
    update_kubeconfig
    echo ""
    
    # Step 4: External Secrets Operator
    deploy_external_secrets
    echo ""
    
    # Step 5: Configure secrets
    configure_secrets
    echo ""
    
    # Step 6: OpenTelemetry Demo
    deploy_otel_demo
    echo ""
    
    # Step 7: Status
    show_status
    
    log_success "🎉 Deployment complete!"
    echo ""
    log_info "Next steps:"
    echo "  1. Wait for ALB to be provisioned (may take 5-10 minutes)"
    echo "  2. Get ALB DNS: kubectl get ingress -n otel-demo"
    echo "  3. Access the demo at: http://<ALB-DNS>/"
    echo "  4. Trigger incidents: ./incidentfox/scripts/trigger-incident.sh --help"
    echo "  5. Connect your agent: see incidentfox/docs/agent-integration.md"
}

# Parse command
COMMAND="${1:-deploy}"

case "$COMMAND" in
    deploy)
        deploy_all
        ;;
    destroy)
        destroy_all
        ;;
    status)
        show_status
        ;;
    kubeconfig)
        update_kubeconfig
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  deploy     - Deploy/update everything (default)"
        echo "  destroy    - Tear down everything"
        echo "  status     - Show deployment status"
        echo "  kubeconfig - Update local kubeconfig"
        exit 1
        ;;
esac

