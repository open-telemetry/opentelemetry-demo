# Complete Example: Account Creation + SLO Setup
#
# This example shows how to use both modules together in a single configuration.
# Note: The SLO creation will fail if the checkout service isn't reporting yet.
# Consider applying in two stages or using the separate examples.
#
# Usage:
#   1. Set environment variables:
#      export NEW_RELIC_API_KEY="your-user-api-key"
#      export NEW_RELIC_ACCOUNT_ID="your-parent-account-id"
#      export NEW_RELIC_REGION="US"
#
#   2. Stage 1 - Create account and deploy demo:
#      terraform init
#      terraform apply -target=module.account_management
#      export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)
#      cd ../../../scripts && ./install-k8s.sh && cd -
#
#   3. Wait 2-5 minutes for data to appear
#
#   4. Stage 2 - Create SLO:
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
  # NEW_RELIC_API_KEY, NEW_RELIC_ACCOUNT_ID, NEW_RELIC_REGION
}

# Module 1: Create account and license key
module "account_management" {
  source = "../../account_management"

  subaccount_name = "OpenTelemetry Demo - Complete Example"
  region          = "us"
}

# Module 2: Create SLO (apply after demo is deployed)
module "newrelic_demo" {
  source = "../../newrelic_demo"

  account_id = module.account_management.account_id

  # This module depends on the demo being deployed and reporting
  # Consider using terraform apply -target to apply in stages
}

# Outputs from account_management
output "account_id" {
  description = "The created New Relic account ID"
  value       = module.account_management.account_id
}

output "license_key" {
  description = "License key for deploying the demo"
  value       = module.account_management.license_key
  sensitive   = true
}

# Outputs from newrelic_demo
output "slo_id" {
  description = "The created SLO ID"
  value       = module.newrelic_demo.slo_id
}

output "checkout_service_guid" {
  description = "The checkout service GUID"
  value       = module.newrelic_demo.checkout_service_guid
}

output "deployment_guide" {
  description = "Step-by-step deployment guide"
  value       = <<-EOT

    ===== Deployment Guide =====

    Stage 1 - Create Account:
      terraform apply -target=module.account_management

    Stage 2 - Deploy Demo:
      export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)
      cd ../../../scripts
      ./install-k8s.sh

    Stage 3 - Wait for data (2-5 minutes)
      kubectl get pods -n opentelemetry-demo

    Stage 4 - Create SLO:
      cd -  # Return to terraform directory
      terraform apply

  EOT
}
