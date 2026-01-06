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
# Uses Azure-provided domain (AzureManagedDomain) for quick setup
# For production, consider using a custom domain
resource "azurerm_email_communication_service_domain" "azure_managed" {
  name              = "AzureManagedDomain"
  email_service_id  = azurerm_email_communication_service.this.id
  domain_management = "AzureManagedDomain"

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
# Entra ID Application for SMTP Authentication
# -----------------------------------------------------------------------------
# Azure Communication Services SMTP requires Entra ID authentication
resource "azuread_application" "smtp" {
  display_name = "${var.communication_service_name}-smtp-auth"

  required_resource_access {
    # Azure Communication Services
    resource_app_id = "1fd5118e-2576-4263-8130-9503064c837a"

    resource_access {
      id   = "5b89695c-b5cb-4fc5-9f9a-8b43db5bfa33" # Mail.Send
      type = "Scope"
    }
  }

  tags = ["terraform", "otel-demo", "smtp-auth"]
}

resource "azuread_service_principal" "smtp" {
  client_id = azuread_application.smtp.client_id
}

resource "azuread_application_password" "smtp" {
  application_id = azuread_application.smtp.id
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
  scope                = azurerm_communication_service.this.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.smtp.object_id
}
