variable "online_subscription_id" {
  description = "Subscription placed in the Online landing zone (runs the otel-demo AKS app)."
  type        = string
}

variable "online_dev_subscription_id" {
  description = "Second subscription placed in the Online landing zone."
  type        = string
}

variable "corp_subscription_id" {
  description = "Subscription placed in the Corp landing zone."
  type        = string
}

variable "sherlocks_principal_id" {
  description = "Object id of the service principal Sherlocks scans with (gets Reader at otel-demo-alz)."
  type        = string
}

variable "location" {
  type    = string
  default = "centralindia"
}

variable "tags" {
  type    = map(string)
  default = { purpose = "otel-demo-playground" }
}
