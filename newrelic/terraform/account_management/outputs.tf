output "account_id" {
  description = "The ID of the created New Relic sub-account"
  value       = newrelic_account_management.subaccount.id
}

output "account_name" {
  description = "The name of the created New Relic sub-account"
  value       = newrelic_account_management.subaccount.name
}

output "license_key" {
  description = "The New Relic license key for ingesting data. Export as: export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)"
  value       = newrelic_api_access_key.license_key.key
  sensitive   = true
}

output "region" {
  description = "The region where the sub-account was created"
  value       = newrelic_account_management.subaccount.region
}
