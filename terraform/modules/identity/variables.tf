# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

variable "identity_name" {
  description = "Name of the User-Assigned Managed Identity"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region for the managed identity"
  type        = string
}

variable "oidc_issuer_url" {
  description = "OIDC issuer URL from AKS cluster for workload identity federation"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace where the service account is created"
  type        = string
  default     = "otel-demo"
}

variable "service_account_name" {
  description = "Name of the Kubernetes service account to federate"
  type        = string
  default     = "otel-collector-sa"
}

variable "adx_cluster_id" {
  description = "ID of the ADX cluster for role assignment"
  type        = string
}

variable "adx_database_name" {
  description = "Name of the ADX database"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
