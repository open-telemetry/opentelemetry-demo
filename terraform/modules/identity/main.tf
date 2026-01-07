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
# Wait for AAD Propagation
# Managed identities need time to propagate through Azure AD
# =============================================================================

resource "time_sleep" "wait_for_identity" {
  depends_on = [azurerm_user_assigned_identity.otel_collector]

  create_duration = "60s"
}

# =============================================================================
# ADX Database Principal Assignment
# Grant the Managed Identity access to the ADX database
# =============================================================================

resource "azurerm_kusto_database_principal_assignment" "otel_ingestor" {
  depends_on = [time_sleep.wait_for_identity]
  name                = "otel-collector-ingestor"
  resource_group_name = split("/", var.adx_cluster_id)[4]
  cluster_name        = split("/", var.adx_cluster_id)[8]
  database_name       = var.adx_database_name

  tenant_id      = data.azurerm_client_config.current.tenant_id
  # ADX requires the client_id (application ID), not principal_id (object ID)
  principal_id   = azurerm_user_assigned_identity.otel_collector.client_id
  principal_type = "App"
  role           = "Ingestor"
}

resource "azurerm_kusto_database_principal_assignment" "otel_viewer" {
  depends_on = [time_sleep.wait_for_identity]
  name                = "otel-collector-viewer"
  resource_group_name = split("/", var.adx_cluster_id)[4]
  cluster_name        = split("/", var.adx_cluster_id)[8]
  database_name       = var.adx_database_name

  tenant_id      = data.azurerm_client_config.current.tenant_id
  # ADX requires the client_id (application ID), not principal_id (object ID)
  principal_id   = azurerm_user_assigned_identity.otel_collector.client_id
  principal_type = "App"
  role           = "Viewer"
}

# =============================================================================
# Grafana ADX Service Principal
# The ADX Grafana plugin v7.2.1 doesn't support Workload Identity,
# so we need a traditional Service Principal with client secret
# =============================================================================

resource "azuread_application" "grafana_adx" {
  display_name = "${var.identity_name}-grafana-adx"
  owners       = [data.azurerm_client_config.current.object_id]
}

resource "azuread_service_principal" "grafana_adx" {
  client_id                    = azuread_application.grafana_adx.client_id
  app_role_assignment_required = false
  owners                       = [data.azurerm_client_config.current.object_id]
}

resource "azuread_application_password" "grafana_adx" {
  application_id = azuread_application.grafana_adx.id
  display_name   = "grafana-adx-secret"
  end_date       = timeadd(timestamp(), "8760h") # 1 year
}

# Wait for Service Principal propagation
resource "time_sleep" "wait_for_grafana_sp" {
  depends_on = [azuread_service_principal.grafana_adx]

  create_duration = "60s"
}

# Grant Grafana Service Principal Viewer access to ADX
resource "azurerm_kusto_database_principal_assignment" "grafana_viewer" {
  depends_on = [time_sleep.wait_for_grafana_sp]
  name                = "grafana-adx-viewer"
  resource_group_name = split("/", var.adx_cluster_id)[4]
  cluster_name        = split("/", var.adx_cluster_id)[8]
  database_name       = var.adx_database_name

  tenant_id      = data.azurerm_client_config.current.tenant_id
  principal_id   = azuread_application.grafana_adx.client_id
  principal_type = "App"
  role           = "Viewer"
}
