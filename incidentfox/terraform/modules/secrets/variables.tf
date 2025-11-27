variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "secrets_prefix" {
  description = "Prefix for secret names"
  type        = string
}

variable "secrets" {
  description = "Map of secrets to create"
  type = map(object({
    description = string
    secret_data = map(string)
  }))
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

