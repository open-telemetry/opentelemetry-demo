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
