variable "account_id" {
  description = "The New Relic account ID where the OpenTelemetry Demo is deployed"
  type        = string
}

variable "checkout_service_name" {
  description = "Name of the checkout service entity in New Relic"
  type        = string
  default     = "checkout"
}
