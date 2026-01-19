# Example: Create a New Relic sub-account for the OpenTelemetry Demo
#
# Usage:
#   1. Set environment variables:
#      export NEW_RELIC_API_KEY="your-user-api-key"
#      export NEW_RELIC_ACCOUNT_ID="your-parent-account-id"
#      export NEW_RELIC_REGION="US"
#
#   2. Initialize and apply:
#      terraform init
#      terraform apply
#
#   3. Export the license key and deploy:
#      export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)
#      cd ../../../scripts
#      ./install-k8s.sh

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

module "account_management" {
  source = "../../account_management"

  subaccount_name = "OpenTelemetry Demo Environment"
  region          = "us"  # or "eu"
}

output "account_id" {
  description = "Use this account ID for the newrelic_demo module"
  value       = module.account_management.account_id
}

output "account_name" {
  description = "Name of the created sub-account"
  value       = module.account_management.account_name
}

output "license_key" {
  description = "Export as: export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)"
  value       = module.account_management.license_key
  sensitive   = true
}

output "next_steps" {
  description = "What to do next"
  value       = <<-EOT

    ===== Next Steps =====

    1. Export the license key:
       export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)

    2. Deploy the OpenTelemetry Demo:
       cd ../../../scripts
       ./install-k8s.sh

    3. Wait 2-5 minutes for the demo to start reporting data

    4. Create the SLO:
       cd ../terraform/examples/newrelic_demo
       # Update main.tf with your account_id
       terraform init && terraform apply

  EOT
}
