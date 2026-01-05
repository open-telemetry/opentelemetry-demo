# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# =============================================================================
# Resource Group Outputs
# =============================================================================

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Location of the resource group"
  value       = azurerm_resource_group.main.location
}

# =============================================================================
# Azure Data Explorer Outputs
# =============================================================================

output "adx_cluster_name" {
  description = "Name of the ADX cluster"
  value       = module.adx.cluster_name
}

output "adx_cluster_uri" {
  description = "URI of the ADX cluster"
  value       = module.adx.cluster_uri
}

output "adx_ingestion_uri" {
  description = "Data ingestion URI of the ADX cluster"
  value       = module.adx.cluster_data_ingestion_uri
}

output "adx_database_name" {
  description = "Name of the ADX database"
  value       = module.adx.database_name
}

# =============================================================================
# Azure Kubernetes Service Outputs
# =============================================================================

output "aks_cluster_name" {
  description = "Name of the AKS cluster"
  value       = module.aks.cluster_name
}

output "aks_cluster_fqdn" {
  description = "FQDN of the AKS cluster"
  value       = module.aks.cluster_fqdn
}

output "aks_oidc_issuer_url" {
  description = "OIDC issuer URL for workload identity"
  value       = module.aks.oidc_issuer_url
}

output "aks_get_credentials_command" {
  description = "Azure CLI command to get AKS credentials"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.main.name} --name ${module.aks.cluster_name}"
}

# =============================================================================
# Workload Identity Outputs
# =============================================================================

output "workload_identity_client_id" {
  description = "Client ID of the Managed Identity (for workload identity annotation)"
  value       = module.identity.client_id
}

output "workload_identity_name" {
  description = "Name of the User-Assigned Managed Identity"
  value       = module.identity.identity_name
}

output "tenant_id" {
  description = "Azure AD Tenant ID"
  value       = module.identity.tenant_id
}

# =============================================================================
# Grafana ADX Service Principal Outputs
# =============================================================================

output "grafana_adx_client_id" {
  description = "Client ID of the Grafana ADX Service Principal"
  value       = module.identity.grafana_adx_client_id
}

output "grafana_adx_client_secret" {
  description = "Client Secret of the Grafana ADX Service Principal"
  value       = module.identity.grafana_adx_client_secret
  sensitive   = true
}

# =============================================================================
# Helm Installation Command
# =============================================================================

output "helm_install_command" {
  description = "Helm command to deploy the OpenTelemetry Demo"
  value       = "helm install otel-demo ./kubernetes/opentelemetry-demo-chart -f ./kubernetes/opentelemetry-demo-chart/values-generated.yaml -n otel-demo --create-namespace"
}

output "next_steps" {
  description = "Next steps after Terraform deployment"
  value       = <<-EOT

    ================================================================================
    DEPLOYMENT COMPLETE - WORKLOAD IDENTITY ENABLED!
    ================================================================================

    Terraform has created:
    - AKS cluster with OIDC issuer and Workload Identity enabled
    - User-Assigned Managed Identity with ADX permissions
    - Federated Identity Credential linking K8s service account to the identity
    - values-generated.yaml with Workload Identity configuration

    NO SECRETS REQUIRED! Authentication uses Azure AD Workload Identity.

    DEPLOY WITH HELM
    ----------------

    1. Get AKS credentials:
       az aks get-credentials --resource-group ${azurerm_resource_group.main.name} --name ${module.aks.cluster_name}

    2. Deploy with Helm using generated values:
       helm install otel-demo ./kubernetes/opentelemetry-demo-chart \
         -f ./kubernetes/opentelemetry-demo-chart/values-generated.yaml \
         -n otel-demo --create-namespace

    3. Verify pods are running:
       kubectl get pods -n otel-demo

    4. Access the demo:
       kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080
       kubectl port-forward -n otel-demo svc/grafana 3000:80

    ================================================================================
    WORKLOAD IDENTITY CONFIGURATION
    ================================================================================

    Managed Identity Client ID: ${module.identity.client_id}
    OIDC Issuer URL: ${module.aks.oidc_issuer_url}
    Federated Service Account: system:serviceaccount:otel-demo:otel-collector-sa

    The OTel Collector pod will automatically authenticate to ADX using:
    - azure.workload.identity/use: "true" label
    - azure.workload.identity/client-id annotation on service account
    - Projected service account token volume (auto-mounted by AKS)

    ADX Cluster URI: ${module.adx.cluster_uri}
    ADX Database: ${module.adx.database_name}
    AKS Cluster: ${module.aks.cluster_name}

  EOT
}
