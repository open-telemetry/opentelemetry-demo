# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

output "cluster_id" {
  description = "ID of the ADX cluster"
  value       = azurerm_kusto_cluster.main.id
}

output "cluster_name" {
  description = "Name of the ADX cluster"
  value       = azurerm_kusto_cluster.main.name
}

output "cluster_uri" {
  description = "URI of the ADX cluster"
  value       = azurerm_kusto_cluster.main.uri
}

output "cluster_data_ingestion_uri" {
  description = "Data ingestion URI of the ADX cluster"
  value       = azurerm_kusto_cluster.main.data_ingestion_uri
}

output "database_name" {
  description = "Name of the database"
  value       = azurerm_kusto_database.otel.name
}

output "database_id" {
  description = "ID of the database"
  value       = azurerm_kusto_database.otel.id
}

output "cluster_principal_id" {
  description = "Principal ID of the cluster's managed identity"
  value       = azurerm_kusto_cluster.main.identity[0].principal_id
}
