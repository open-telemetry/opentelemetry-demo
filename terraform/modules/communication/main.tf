# =============================================================================
# Azure Communication Services Module
# =============================================================================
# Creates Azure Communication Services with Email capabilities for Grafana alerts

# -----------------------------------------------------------------------------
# Azure Communication Services Resource
# -----------------------------------------------------------------------------
resource "azurerm_communication_service" "this" {
  name                = var.communication_service_name
  resource_group_name = var.resource_group_name
  data_location       = var.data_location

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Email Communication Services
# -----------------------------------------------------------------------------
resource "azurerm_email_communication_service" "this" {
  name                = "${var.communication_service_name}-email"
  resource_group_name = var.resource_group_name
  data_location       = var.data_location

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Azure Managed Email Domain
# -----------------------------------------------------------------------------
# Uses Azure-provided domain (AzureManaged) for quick setup
# For production, consider using a custom domain
resource "azurerm_email_communication_service_domain" "azure_managed" {
  name              = "AzureManagedDomain"
  email_service_id  = azurerm_email_communication_service.this.id
  domain_management = "AzureManaged"

  # Note: Azure managed domains have format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.azurecomm.net
  # The actual domain will be available in outputs after creation

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Link Email Domain to Communication Service
# -----------------------------------------------------------------------------
resource "azurerm_communication_service_email_domain_association" "this" {
  communication_service_id = azurerm_communication_service.this.id
  email_service_domain_id  = azurerm_email_communication_service_domain.azure_managed.id
}

# -----------------------------------------------------------------------------
# Entra ID Application for SMTP Authentication (Optional)
# -----------------------------------------------------------------------------
# Azure Communication Services SMTP requires Entra ID authentication
# These resources require Application Administrator role in Entra ID
# Set var.create_smtp_entra_app = false to skip and configure manually

resource "azuread_application" "smtp" {
  count        = var.create_smtp_entra_app ? 1 : 0
  display_name = "${var.communication_service_name}-smtp-auth"

  tags = ["terraform", "otel-demo", "smtp-auth"]
}

resource "azuread_service_principal" "smtp" {
  count     = var.create_smtp_entra_app ? 1 : 0
  client_id = azuread_application.smtp[0].client_id
}

resource "azuread_application_password" "smtp" {
  count          = var.create_smtp_entra_app ? 1 : 0
  application_id = azuread_application.smtp[0].id
  display_name   = "SMTP Authentication Secret"
  end_date       = timeadd(timestamp(), "8760h") # 1 year

  lifecycle {
    ignore_changes = [end_date]
  }
}

# -----------------------------------------------------------------------------
# Role Assignment for SMTP
# -----------------------------------------------------------------------------
# Grant the Entra app permission to send emails via the Communication Service
resource "azurerm_role_assignment" "smtp_contributor" {
  count                = var.create_smtp_entra_app ? 1 : 0
  scope                = azurerm_communication_service.this.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.smtp[0].object_id
}
