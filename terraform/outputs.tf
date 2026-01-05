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

output "aks_get_credentials_command" {
  description = "Azure CLI command to get AKS credentials"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.main.name} --name ${module.aks.cluster_name}"
}

# =============================================================================
# Service Principal Outputs
# =============================================================================

output "service_principal_client_id" {
  description = "Client ID of the service principal"
  value       = module.identity.client_id
}

output "service_principal_tenant_id" {
  description = "Tenant ID for the service principal"
  value       = module.identity.tenant_id
}

output "service_principal_secret_expiry" {
  description = "Expiry date of the service principal secret"
  value       = module.identity.password_expiry
}

# =============================================================================
# Deployment Instructions
# =============================================================================

# =============================================================================
# Helm Installation Command
# =============================================================================

output "helm_install_command" {
  description = "Helm command to deploy the OpenTelemetry Demo"
  value       = "helm install otel-demo ./kubernetes/opentelemetry-demo-chart -f ./kubernetes/opentelemetry-demo-chart/values-generated.yaml"
}

output "next_steps" {
  description = "Next steps after Terraform deployment"
  value       = <<-EOT

    ================================================================================
    DEPLOYMENT COMPLETE!
    ================================================================================

    Terraform has generated:
    - kubernetes/azure/secrets.yaml (K8s secret with ADX credentials)
    - kubernetes/opentelemetry-demo-chart/values-generated.yaml (Helm values)

    OPTION 1: Deploy with Helm (Recommended)
    ----------------------------------------

    1. Get AKS credentials:
       az aks get-credentials --resource-group ${azurerm_resource_group.main.name} --name ${module.aks.cluster_name}

    2. Deploy with Helm using generated values:
       helm install otel-demo ./kubernetes/opentelemetry-demo-chart \
         -f ./kubernetes/opentelemetry-demo-chart/values-generated.yaml

    3. Verify pods are running:
       kubectl get pods -n otel-demo

    4. Access the demo:
       kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080
       kubectl port-forward -n otel-demo svc/grafana 3000:3000

    OPTION 2: Deploy with kubectl
    -----------------------------

    1. Get AKS credentials:
       az aks get-credentials --resource-group ${azurerm_resource_group.main.name} --name ${module.aks.cluster_name}

    2. Create namespace and apply secrets:
       kubectl create namespace otel-demo
       kubectl apply -f kubernetes/azure/secrets.yaml

    3. Deploy with Helm:
       helm install otel-demo ./kubernetes/opentelemetry-demo-chart \
         --set azure.existingSecret=adx-credentials \
         --set adx.clusterUri=${module.adx.cluster_uri}

    ================================================================================
    IMPORTANT INFORMATION
    ================================================================================

    ADX Cluster URI: ${module.adx.cluster_uri}
    ADX Database: ${module.adx.database_name}
    AKS Cluster: ${module.aks.cluster_name}
    Service Principal Secret Expires: ${module.identity.password_expiry}

    Remember to rotate the service principal secret before it expires!

  EOT
}
