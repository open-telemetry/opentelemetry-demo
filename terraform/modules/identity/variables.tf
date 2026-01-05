# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

variable "application_name" {
  description = "Name of the Azure AD application"
  type        = string
}

variable "password_rotation_days" {
  description = "Number of days before the password expires"
  type        = number
  default     = 180
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
  description = "Tags to apply (for documentation purposes)"
  type        = map(string)
  default     = {}
}
