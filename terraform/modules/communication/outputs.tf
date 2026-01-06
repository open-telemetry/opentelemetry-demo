# =============================================================================
# Azure Communication Services Module Outputs
# =============================================================================

output "communication_service_id" {
  description = "ID of the Azure Communication Services resource"
  value       = azurerm_communication_service.this.id
}

output "communication_service_name" {
  description = "Name of the Azure Communication Services resource"
  value       = azurerm_communication_service.this.name
}

# -----------------------------------------------------------------------------
# SMTP Configuration for Grafana
# -----------------------------------------------------------------------------
# Azure Communication Services SMTP endpoint
output "smtp_host" {
  description = "SMTP host for Azure Communication Services"
  value       = "smtp.azurecomm.net"
}

output "smtp_port" {
  description = "SMTP port (TLS required)"
  value       = 587
}

# SMTP username format: <Azure Communication Services Resource name>.<Entra Application ID>.<Entra Tenant ID>
output "smtp_username" {
  description = "SMTP username for authentication. Empty if create_smtp_entra_app is false."
  value       = var.create_smtp_entra_app ? "${azurerm_communication_service.this.name}.${azuread_application.smtp[0].client_id}.${var.tenant_id}" : ""
}

output "smtp_password" {
  description = "SMTP password (Entra app secret). Empty if create_smtp_entra_app is false."
  value       = var.create_smtp_entra_app ? azuread_application_password.smtp[0].value : ""
  sensitive   = true
}

output "smtp_entra_app_created" {
  description = "Whether the Entra ID app for SMTP was created"
  value       = var.create_smtp_entra_app
}

# -----------------------------------------------------------------------------
# Email Domain Configuration
# -----------------------------------------------------------------------------
output "email_domain" {
  description = "Azure managed email domain"
  value       = azurerm_email_communication_service_domain.azure_managed.from_sender_domain
}

output "from_email_address" {
  description = "Default from email address for alerts"
  value       = "DoNotReply@${azurerm_email_communication_service_domain.azure_managed.from_sender_domain}"
}

# -----------------------------------------------------------------------------
# Full SMTP Configuration Object
# -----------------------------------------------------------------------------
output "grafana_smtp_config" {
  description = "Complete SMTP configuration for Grafana helm values. If Entra app not created, user/password will be empty."
  value = {
    enabled     = var.create_smtp_entra_app
    host        = "smtp.azurecomm.net"
    port        = 587
    user        = var.create_smtp_entra_app ? "${azurerm_communication_service.this.name}.${azuread_application.smtp[0].client_id}.${var.tenant_id}" : ""
    password    = var.create_smtp_entra_app ? azuread_application_password.smtp[0].value : ""
    fromAddress = "DoNotReply@${azurerm_email_communication_service_domain.azure_managed.from_sender_domain}"
    fromName    = "OTel Demo Alerts"
    skipVerify  = false
  }
  sensitive = true
}
