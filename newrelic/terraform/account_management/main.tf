provider "newrelic" {
  api_key    = var.newrelic_api_key
  account_id = var.newrelic_parent_account_id
  region     = upper(var.newrelic_region)
}

# Create a New Relic sub-account
resource "newrelic_account_management" "subaccount" {
  name   = var.subaccount_name
  region = lower(var.newrelic_region)
}

# Create a license key for the sub-account
resource "newrelic_api_access_key" "license_key" {
  account_id  = newrelic_account_management.subaccount.id
  key_type    = "INGEST"
  ingest_type = "LICENSE"
  name        = "OpenTelemetry Demo License Key"
  notes       = "License key for OpenTelemetry Demo deployment"

  depends_on = [
    newrelic_account_management.subaccount
  ]
}
