# Printed by `terraform output`. The first four go into the env: block of
# .github/workflows/azure-deploy.yml.

output "azure_client_id" {
  value = azuread_application.github_ci.client_id
}

output "azure_tenant_id" {
  value = azuread_service_principal.github_ci.application_tenant_id
}

output "azure_subscription_id" {
  value = var.subscription_id
}

output "acr_name" {
  value = azurerm_container_registry.acr.name
}

output "kubeconfig_command" {
  value = "az aks get-credentials -g ${azurerm_resource_group.demo.name} -n ${azurerm_kubernetes_cluster.aks.name} --file ~/.kube/otel-demo-aks.config"
}

# Goes into deploy/azure/secrets.env. Hidden unless asked for:
#   terraform output -raw appinsights_connection_string
output "appinsights_connection_string" {
  value     = azurerm_application_insights.appi.connection_string
  sensitive = true
}
