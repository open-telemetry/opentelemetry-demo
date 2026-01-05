# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region for the ADX cluster"
  type        = string
}

variable "cluster_name" {
  description = "Name of the ADX cluster"
  type        = string
}

variable "sku_name" {
  description = "SKU name for the ADX cluster"
  type        = string
  default     = "Dev(No SLA)_Standard_D11_v2"
}

variable "sku_capacity" {
  description = "Number of instances in the cluster"
  type        = number
  default     = 1
}

variable "database_name" {
  description = "Name of the database"
  type        = string
}

variable "hot_cache_days" {
  description = "Hot cache period in days"
  type        = number
  default     = 30
}

variable "retention_days" {
  description = "Soft delete period in days"
  type        = number
  default     = 365
}

variable "auto_stop_enabled" {
  description = "Enable auto-stop when cluster is idle"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
