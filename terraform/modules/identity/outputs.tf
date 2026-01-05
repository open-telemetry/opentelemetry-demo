# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

output "application_id" {
  description = "Application (client) ID of the Azure AD application"
  value       = azuread_application.otel_collector.client_id
}

output "application_object_id" {
  description = "Object ID of the Azure AD application"
  value       = azuread_application.otel_collector.object_id
}

output "service_principal_id" {
  description = "Object ID of the service principal"
  value       = azuread_service_principal.otel_collector.object_id
}

output "client_id" {
  description = "Client ID for authentication"
  value       = azuread_application.otel_collector.client_id
}

output "client_secret" {
  description = "Client secret for authentication"
  value       = azuread_application_password.otel_collector.value
  sensitive   = true
}

output "tenant_id" {
  description = "Azure AD tenant ID"
  value       = data.azurerm_client_config.current.tenant_id
}

output "password_expiry" {
  description = "Expiry date of the client secret"
  value       = azuread_application_password.otel_collector.end_date
}
