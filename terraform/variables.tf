# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# =============================================================================
# General Configuration
# =============================================================================

variable "project_name" {
  description = "Name of the project, used as prefix for all resources"
  type        = string
  default     = "otel-demo"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "OpenTelemetry Demo"
    Purpose     = "ADX Observability"
    ManagedBy   = "Terraform"
  }
}

# =============================================================================
# Azure Data Explorer Configuration
# =============================================================================

variable "adx_sku_name" {
  description = "SKU name for ADX cluster (Dev(No SLA)_Standard_D11_v2 for dev, Standard_D11_v2 for prod)"
  type        = string
  default     = "Dev(No SLA)_Standard_D11_v2"
}

variable "adx_sku_capacity" {
  description = "Number of instances in the ADX cluster"
  type        = number
  default     = 1
}

variable "adx_database_name" {
  description = "Name of the ADX database for telemetry data"
  type        = string
  default     = "otel_demo"
}

variable "adx_hot_cache_days" {
  description = "Number of days to keep data in hot cache"
  type        = number
  default     = 30
}

variable "adx_retention_days" {
  description = "Number of days to retain data (soft delete)"
  type        = number
  default     = 365
}

variable "adx_auto_stop_enabled" {
  description = "Enable auto-stop for the ADX cluster when idle"
  type        = bool
  default     = true
}

# =============================================================================
# Azure Kubernetes Service Configuration
# =============================================================================

variable "aks_kubernetes_version" {
  description = "Kubernetes version for AKS cluster"
  type        = string
  default     = "1.29"
}

variable "aks_default_node_pool_vm_size" {
  description = "VM size for the default node pool"
  type        = string
  default     = "Standard_DS2_v2"
}

variable "aks_default_node_pool_count" {
  description = "Number of nodes in the default node pool"
  type        = number
  default     = 3
}

variable "aks_default_node_pool_min_count" {
  description = "Minimum number of nodes for autoscaling"
  type        = number
  default     = 2
}

variable "aks_default_node_pool_max_count" {
  description = "Maximum number of nodes for autoscaling"
  type        = number
  default     = 5
}

variable "aks_enable_auto_scaling" {
  description = "Enable autoscaling for the default node pool"
  type        = bool
  default     = true
}

# =============================================================================
# Service Principal Configuration
# =============================================================================

variable "sp_password_rotation_days" {
  description = "Number of days before service principal password expires"
  type        = number
  default     = 180
}

# =============================================================================
# Networking Configuration
# =============================================================================

variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "aks_subnet_address_prefix" {
  description = "Address prefix for the AKS subnet"
  type        = string
  default     = "10.0.1.0/24"
}
