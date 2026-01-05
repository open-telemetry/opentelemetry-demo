# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# =============================================================================
# Data Sources
# =============================================================================

data "azuread_client_config" "current" {}

data "azurerm_client_config" "current" {}

# =============================================================================
# Azure AD Application for Service Principal
# =============================================================================

resource "azuread_application" "otel_collector" {
  display_name = var.application_name
  owners       = [data.azuread_client_config.current.object_id]

  # API permissions for ADX
  required_resource_access {
    resource_app_id = "2746ea77-4702-4b45-80ca-3c97e680e8b7" # Azure Data Explorer

    resource_access {
      id   = "f7d6c5e8-5f2e-4f4e-8b3d-3c2a1b0f9e8d" # user_impersonation
      type = "Scope"
    }
  }

  tags = ["OpenTelemetry", "ADX", "Observability"]
}

# =============================================================================
# Service Principal
# =============================================================================

resource "azuread_service_principal" "otel_collector" {
  client_id                    = azuread_application.otel_collector.client_id
  app_role_assignment_required = false
  owners                       = [data.azuread_client_config.current.object_id]

  tags = ["OpenTelemetry", "ADX", "Observability"]
}

# =============================================================================
# Service Principal Password (Client Secret)
# =============================================================================

resource "time_rotating" "password_rotation" {
  rotation_days = var.password_rotation_days
}

resource "azuread_application_password" "otel_collector" {
  application_id = azuread_application.otel_collector.id
  display_name   = "otel-collector-secret"

  rotate_when_changed = {
    rotation = time_rotating.password_rotation.id
  }

  end_date_relative = "${var.password_rotation_days * 24}h"
}

# =============================================================================
# ADX Database Principal Assignment
# =============================================================================

# Grant the service principal access to the ADX database
resource "azurerm_kusto_database_principal_assignment" "otel_ingestor" {
  name                = "otel-collector-ingestor"
  resource_group_name = split("/", var.adx_cluster_id)[4]
  cluster_name        = split("/", var.adx_cluster_id)[8]
  database_name       = var.adx_database_name

  tenant_id      = data.azurerm_client_config.current.tenant_id
  principal_id   = azuread_service_principal.otel_collector.object_id
  principal_type = "App"
  role           = "Ingestor"
}

resource "azurerm_kusto_database_principal_assignment" "otel_viewer" {
  name                = "otel-collector-viewer"
  resource_group_name = split("/", var.adx_cluster_id)[4]
  cluster_name        = split("/", var.adx_cluster_id)[8]
  database_name       = var.adx_database_name

  tenant_id      = data.azurerm_client_config.current.tenant_id
  principal_id   = azuread_service_principal.otel_collector.object_id
  principal_type = "App"
  role           = "Viewer"
}
