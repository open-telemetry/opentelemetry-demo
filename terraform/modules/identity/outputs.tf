# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

output "identity_id" {
  description = "ID of the User-Assigned Managed Identity"
  value       = azurerm_user_assigned_identity.otel_collector.id
}

output "identity_name" {
  description = "Name of the User-Assigned Managed Identity"
  value       = azurerm_user_assigned_identity.otel_collector.name
}

output "client_id" {
  description = "Client ID of the Managed Identity (used for workload identity annotation)"
  value       = azurerm_user_assigned_identity.otel_collector.client_id
}

output "principal_id" {
  description = "Principal ID (Object ID) of the Managed Identity"
  value       = azurerm_user_assigned_identity.otel_collector.principal_id
}

output "tenant_id" {
  description = "Azure AD tenant ID"
  value       = data.azurerm_client_config.current.tenant_id
}

output "federated_credential_id" {
  description = "ID of the Federated Identity Credential"
  value       = azurerm_federated_identity_credential.otel_collector.id
}
