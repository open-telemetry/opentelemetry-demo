# =============================================================================
# Azure Communication Services Module Variables
# =============================================================================

variable "communication_service_name" {
  description = "Name of the Azure Communication Services resource"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "data_location" {
  description = "Data location for the communication service (e.g., United States, Europe, UK, Australia, Japan, etc.)"
  type        = string
  default     = "United States"

  validation {
    condition = contains([
      "Africa",
      "Asia Pacific",
      "Australia",
      "Brazil",
      "Canada",
      "Europe",
      "France",
      "Germany",
      "India",
      "Japan",
      "Korea",
      "Norway",
      "Switzerland",
      "UAE",
      "UK",
      "United States"
    ], var.data_location)
    error_message = "Data location must be a valid Azure Communication Services region."
  }
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "tenant_id" {
  description = "Azure AD Tenant ID for SMTP authentication"
  type        = string
}

variable "create_smtp_entra_app" {
  description = "Create Entra ID app for SMTP authentication. Requires Application Administrator role. Set to false to configure SMTP manually."
  type        = bool
  default     = true
}
