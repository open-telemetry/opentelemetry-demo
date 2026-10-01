# Values for this SolarWinds account are in terraform.tfvars. Alerts reach Slack
# through the Logic App in the Azure stack (webhook.tf).

variable "swo_region" {
  description = "SolarWinds data center, as in my.<region>.cloud.solarwinds.com (e.g. ap-01, na-01, eu-01)."
  type        = string
}

variable "cluster_name" {
  description = "k8s.cluster.name the collector stamps on all data. Scopes node and pod alerts to this cluster (the account holds other environments, and node names change on every restart)."
  type        = string
  default     = "otel-demo-aks"
}

variable "namespace" {
  description = "Kubernetes namespace the demo runs in."
  type        = string
  default     = "otel-demo"
}

variable "services" {
  description = <<-EOT
    Demo services the trace-based alerts watch (those metrics carry no cluster
    tag). fraud-detection is left out: it reports 100% errors even when healthy.
  EOT
  type        = list(string)
  default = [
    "accounting", "ad", "cart", "checkout", "currency", "email", "frontend",
    "frontend-proxy", "image-provider", "payment", "product-catalog", "quote",
    "recommendation", "shipping",
  ]
}

variable "error_rate_threshold_pct" {
  description = "Endpoint error-rate threshold. Healthy demo endpoints sit at 0–50%, so this is set high."
  type        = number
  default     = 90
}

variable "latency_threshold_seconds" {
  description = "Average request duration per endpoint that counts as slow. cart EmptyCart normally averages ~0.19 s."
  type        = number
  default     = 0.5
}

variable "memory_exhaustion_exclude_deployments" {
  description = "Deployments that normally run near their memory limit (cache and database), left out of the memory alert."
  type        = list(string)
  default     = ["valkey-cart", "astronomy-db"]
}
