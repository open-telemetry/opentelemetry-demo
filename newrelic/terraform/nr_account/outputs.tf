output "account_id" {
  description = "The ID of the created New Relic sub-account"
  value       = newrelic_account_management.subaccount.id
}

output "license_key" {
  description = "The New Relic license key for ingesting data. Export as: export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)"
  value       = newrelic_api_access_key.license_key.key
  sensitive   = true
}

output "readonly_user_email" {
  description = "Email address of the created read-only user"
  value       = newrelic_user.readonly_user.email_id
}
