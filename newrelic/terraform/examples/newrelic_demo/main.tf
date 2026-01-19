# Example: Create an SLO for the OpenTelemetry Demo checkout service
#
# Prerequisites:
#   - OpenTelemetry Demo is deployed and reporting to New Relic
#   - Checkout service is visible in New Relic (wait 2-5 minutes after deployment)
#
# Usage:
#   1. Set environment variables:
#      export NEW_RELIC_API_KEY="your-user-api-key"
#      export NEW_RELIC_REGION="US"
#
#   2. Update the account_id below
#
#   3. Initialize and apply:
#      terraform init
#      terraform apply

terraform {
  required_version = ">= 1.0"

  required_providers {
    newrelic = {
      source  = "newrelic/newrelic"
      version = "~> 3.0"
    }
  }
}

provider "newrelic" {
  # Configuration via environment variables:
  # NEW_RELIC_API_KEY, NEW_RELIC_REGION
}

module "newrelic_demo" {
  source = "../../newrelic_demo"

  account_id = "1234567"  # REPLACE WITH YOUR ACCOUNT ID
}

output "checkout_service_guid" {
  description = "GUID of the checkout service"
  value       = module.newrelic_demo.checkout_service_guid
}

output "checkout_service_name" {
  description = "Name of the checkout service"
  value       = module.newrelic_demo.checkout_service_name
}

output "slo_id" {
  description = "ID of the created SLO"
  value       = module.newrelic_demo.slo_id
}

output "slo_name" {
  description = "Name of the created SLO"
  value       = module.newrelic_demo.slo_name
}

output "view_slo" {
  description = "How to view the SLO"
  value       = <<-EOT

    ===== View Your SLO =====

    Your SLO has been created successfully!

    View it in New Relic:
    1. Go to https://one.newrelic.com
    2. Navigate to Service Levels
    3. Find "Checkout Service Availability"

    SLO Details:
    - Target: 99.5% availability
    - Time Window: 1-day rolling
    - Tracks: Server-side spans without errors

  EOT
}
