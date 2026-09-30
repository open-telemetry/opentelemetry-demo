# The identity GitHub Actions uses to deploy. There is no password: Azure trusts
# a token that GitHub issues only to workflows running in var.github_repo on
# var.github_branch ("federated credential", a.k.a. OIDC).

resource "azuread_application" "github_ci" {
  display_name = "otel-demo-github-ci"
}

resource "azuread_service_principal" "github_ci" {
  client_id = azuread_application.github_ci.client_id
}

resource "azuread_application_federated_identity_credential" "github_ci" {
  application_id = azuread_application.github_ci.id
  display_name   = "github-migrateai-otel-demo-azure-branch"
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repo}:ref:refs/heads/${var.github_branch}"
  audiences      = ["api://AzureADTokenExchange"]
}

# What CI may do: push images, and update deployments on the cluster.
resource "azurerm_role_assignment" "github_ci_acr_push" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPush"
  principal_id         = azuread_service_principal.github_ci.object_id
}

resource "azurerm_role_assignment" "github_ci_aks_user" {
  scope                = azurerm_kubernetes_cluster.aks.id
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = azuread_service_principal.github_ci.object_id
}
