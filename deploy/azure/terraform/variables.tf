# Everything you might want to change lives here. Values for this setup are in
# terraform.tfvars; when moving to another Azure account, that is the file to edit.

variable "subscription_id" {
  description = "Azure subscription to create everything in."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "centralindia"
}

variable "resource_group_name" {
  description = "Resource group that holds the whole demo. Deleting it deletes everything."
  type        = string
  default     = "otel-demo-rg"
}

variable "aks_name" {
  type    = string
  default = "otel-demo-aks"
}

variable "aks_dns_prefix" {
  description = "Prefix of the cluster's API address. Changing it rebuilds the cluster."
  type        = string
  default     = "otel-demo"
}

variable "node_vm_size" {
  description = "VM size of the cluster node. Needs vCPU quota for its family in the region."
  type        = string
  default     = "Standard_D4s_v6"
}

variable "node_count" {
  type    = number
  default = 1
}

variable "ssh_public_key_path" {
  description = "Public key installed on the cluster node (Azure requires one)."
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "acr_name" {
  description = "Container registry name. Must be globally unique, lowercase letters and digits only."
  type        = string
}

variable "log_analytics_daily_cap_gb" {
  description = "Stop ingesting Azure logs/telemetry for the day after this many GB (cost guard)."
  type        = number
  default     = 1
}

variable "github_repo" {
  description = "GitHub repo whose Actions may deploy (owner/name)."
  type        = string
  default     = "migrateai/opentelemetry-demo"
}

variable "github_branch" {
  description = "Only pushes to this branch can log in to Azure."
  type        = string
  default     = "azure"
}

variable "tags" {
  type    = map(string)
  default = { purpose = "otel-demo-playground" }
}
