# Provider configuration variables
variable "newrelic_api_key" {
  description = "New Relic User API Key with Organization Manager permissions, and which is part of `admin_group_name`"
  type        = string
  sensitive   = true
}

variable "newrelic_parent_account_id" {
  description = "Parent account ID for creating sub-accounts"
  type        = string
}

variable "newrelic_region" {
  description = "New Relic region (US or EU)"
  type        = string
  default     = "US"

  validation {
    condition     = contains(["US", "EU"], upper(var.newrelic_region))
    error_message = "Region must be either 'US' or 'EU'."
  }
}

# Module variables
variable "subaccount_name" {
  description = "Name of the sub-account to create"
  type        = string
}

variable "admin_authentication_domain_name" {
  description = "Authentication domain containing `admin_group_name` group"
  type        = string
  default     = "Default"
}

variable "admin_group_name" {
  description = "Name of an existing group to grant `admin_role_name` in the new account"
  type        = string
}

variable "admin_role_name" {
  description = "Role to grant `admin_group_name`; must have permissions to create license keys"
  type        = string
  default     = "all_product_admin"
}

variable "readonly_authentication_domain_name" {
  description = "Authentication domain for creating the read-only user (only basic auth supported)"
  type        = string
  default     = "Default"
}

variable "readonly_role_name" {
  description = "Role to grant the readonly group in the new account"
  type        = string
  default     = "read_only"
}

variable "readonly_user_email" {
  description = "Email address of the read-only user to create"
  type        = string
}

variable "readonly_user_name" {
  description = "Display name of the read-only user"
  type        = string
}
