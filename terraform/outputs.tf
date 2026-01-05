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

output "next_steps" {
  description = "Next steps after Terraform deployment"
  value       = <<-EOT

    ================================================================================
    DEPLOYMENT COMPLETE!
    ================================================================================

    Next steps:

    1. Get AKS credentials:
       ${module.aks.cluster_name != "" ? "az aks get-credentials --resource-group ${azurerm_resource_group.main.name} --name ${module.aks.cluster_name}" : ""}

    2. Create the otel-demo namespace:
       kubectl create namespace otel-demo

    3. Apply the generated secrets:
       kubectl apply -f kubernetes/azure/secrets.yaml

    4. Deploy the OpenTelemetry Demo:
       kubectl apply -f kubernetes/opentelemetry-demo-azure.yaml

    5. Verify pods are running:
       kubectl get pods -n otel-demo

    6. Access Grafana (after port-forward):
       kubectl port-forward -n otel-demo svc/grafana 3000:3000
       Open: http://localhost:3000

    ================================================================================
    IMPORTANT INFORMATION
    ================================================================================

    ADX Cluster URI: ${module.adx.cluster_uri}
    ADX Database: ${module.adx.database_name}
    Service Principal Secret Expires: ${module.identity.password_expiry}

    Remember to rotate the service principal secret before it expires!

  EOT
}
