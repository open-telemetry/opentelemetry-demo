# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region for the AKS cluster"
  type        = string
}

variable "cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.29"
}

variable "default_node_pool_name" {
  description = "Name of the default node pool"
  type        = string
  default     = "default"
}

variable "default_node_pool_vm_size" {
  description = "VM size for the default node pool"
  type        = string
  default     = "Standard_DS2_v2"
}

variable "default_node_pool_count" {
  description = "Number of nodes in the default node pool"
  type        = number
  default     = 3
}

variable "default_node_pool_min_count" {
  description = "Minimum number of nodes for autoscaling"
  type        = number
  default     = 2
}

variable "default_node_pool_max_count" {
  description = "Maximum number of nodes for autoscaling"
  type        = number
  default     = 5
}

variable "enable_auto_scaling" {
  description = "Enable autoscaling for the default node pool"
  type        = bool
  default     = true
}

variable "subnet_id" {
  description = "ID of the subnet for AKS nodes"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
