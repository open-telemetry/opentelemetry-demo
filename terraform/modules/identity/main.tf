# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# =============================================================================
# Data Sources
# =============================================================================

data "azurerm_client_config" "current" {}

# =============================================================================
# User-Assigned Managed Identity for Workload Identity
# =============================================================================

resource "azurerm_user_assigned_identity" "otel_collector" {
  name                = var.identity_name
  resource_group_name = var.resource_group_name
  location            = var.location

  tags = var.tags
}

# =============================================================================
# Federated Identity Credential
# Links the Kubernetes Service Account to the Managed Identity
# =============================================================================

resource "azurerm_federated_identity_credential" "otel_collector" {
  name                = "otel-collector-federated"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.otel_collector.id

  # The OIDC issuer from AKS cluster
  issuer = var.oidc_issuer_url

  # The subject identifier - must match the K8s service account
  # Format: system:serviceaccount:<namespace>:<service-account-name>
  subject = "system:serviceaccount:${var.namespace}:${var.service_account_name}"

  # The audience for the token
  audience = ["api://AzureADTokenExchange"]
}

# =============================================================================
# ADX Database Principal Assignment
# Grant the Managed Identity access to the ADX database
# =============================================================================

resource "azurerm_kusto_database_principal_assignment" "otel_ingestor" {
  name                = "otel-collector-ingestor"
  resource_group_name = split("/", var.adx_cluster_id)[4]
  cluster_name        = split("/", var.adx_cluster_id)[8]
  database_name       = var.adx_database_name

  tenant_id      = data.azurerm_client_config.current.tenant_id
  principal_id   = azurerm_user_assigned_identity.otel_collector.principal_id
  principal_type = "App"
  role           = "Ingestor"
}

resource "azurerm_kusto_database_principal_assignment" "otel_viewer" {
  name                = "otel-collector-viewer"
  resource_group_name = split("/", var.adx_cluster_id)[4]
  cluster_name        = split("/", var.adx_cluster_id)[8]
  database_name       = var.adx_database_name

  tenant_id      = data.azurerm_client_config.current.tenant_id
  principal_id   = azurerm_user_assigned_identity.otel_collector.principal_id
  principal_type = "App"
  role           = "Viewer"
}
