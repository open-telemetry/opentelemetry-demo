# Values for this SolarWinds account are in terraform.tfvars; the Slack webhook
# comes from TF_VAR_slack_webhook_url in ../secrets.env.

variable "swo_region" {
  description = "SolarWinds data center, as in my.<region>.cloud.solarwinds.com (e.g. ap-01, na-01, eu-01)."
  type        = string
}

variable "slack_webhook_url" {
  description = "Slack incoming webhook for the alerts channel."
  type        = string
  sensitive   = true
}

variable "namespace" {
  description = "Kubernetes namespace the demo runs in. Alerts only look at this namespace."
  type        = string
  default     = "otel-demo"
}

variable "services" {
  description = <<-EOT
    Demo services the error-rate alert watches. The SolarWinds account also holds
    other environments, so alerts must not match every service. fraud-detection
    is left out: it reports 100% errors even when healthy.
  EOT
  type        = list(string)
  default = [
    "accounting", "ad", "cart", "checkout", "currency", "email", "frontend",
    "frontend-proxy", "image-provider", "payment", "product-catalog", "quote",
    "recommendation", "shipping",
  ]
}

variable "error_rate_threshold_pct" {
  description = "Error-rate alert threshold. Healthy demo services sit at 0–50%, so this is set high."
  type        = number
  default     = 90
}

variable "latency_threshold_seconds" {
  description = "Average HTTP server duration that counts as slow. The frontend normally averages ~0.01 s."
  type        = number
  default     = 1
}
