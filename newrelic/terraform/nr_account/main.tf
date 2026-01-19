provider "newrelic" {
  api_key    = var.newrelic_api_key
  account_id = var.newrelic_parent_account_id
  region     = upper(var.newrelic_region)
}

# Create a New Relic sub-account
resource "newrelic_account_management" "subaccount" {
  name   = var.subaccount_name
  region = upper(var.newrelic_region) == "US" ? "us01" : "eu01"
}

# Get the current user and grant access to the sub-account
resource "terraform_data" "grant_user_access" {
  triggers_replace = {
    account_id = newrelic_account_management.subaccount.id
  }

  provisioner "local-exec" {
    command = "${path.module}/grant_access.sh '${var.newrelic_api_key}' '${upper(var.newrelic_region) == "US" ? "newrelic" : "eu.newrelic"}' '${var.authentication_domain_name}' '${var.admin_group_name}' '${var.admin_role_name}' ${newrelic_account_management.subaccount.id}"
  }

  depends_on = [
    newrelic_account_management.subaccount
  ]
}

# Create a license key for the sub-account
resource "newrelic_api_access_key" "license_key" {
  account_id  = newrelic_account_management.subaccount.id
  key_type    = "INGEST"
  ingest_type = "LICENSE"
  name        = "OpenTelemetry Demo License Key"
  notes       = "License key for OpenTelemetry Demo deployment"

  depends_on = [
    newrelic_account_management.subaccount,
    terraform_data.grant_user_access
  ]
}
