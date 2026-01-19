# Provider configuration variables
variable "newrelic_api_key" {
  description = "New Relic User API Key"
  type        = string
  sensitive   = true
}

variable "newrelic_parent_account_id" {
  description = "Parent New Relic account ID for creating sub-accounts"
  type        = string
}

variable "newrelic_region" {
  description = "New Relic region (US or EU) - used for both provider and sub-account"
  type        = string
  default     = "US"

  validation {
    condition     = contains(["US", "EU"], upper(var.newrelic_region))
    error_message = "Region must be either 'US' or 'EU'."
  }
}

# Module variables
variable "subaccount_name" {
  description = "Name of the New Relic sub-account to create"
  type        = string
}

variable "authentication_domain_name" {
  description = "Name of the authentication domain to use (e.g., 'Default')"
  type        = string
  default     = "Default"
}

variable "admin_group_name" {
  description = "Name of an existing admin group to grant access to the sub-account. The user running Terraform "
  type        = string
}

variable "admin_role_name" {
  description = "Name of the admin role to grant (e.g., 'all_product_admin')"
  type        = string
  default     = "all_product_admin"
}
