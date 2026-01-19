variable "subaccount_name" {
  description = "Name of the New Relic sub-account to create"
  type        = string
}

variable "region" {
  description = "Region for the sub-account (us or eu)"
  type        = string
  default     = "us"

  validation {
    condition     = contains(["us", "eu"], lower(var.region))
    error_message = "Region must be either 'us' or 'eu'."
  }
}
