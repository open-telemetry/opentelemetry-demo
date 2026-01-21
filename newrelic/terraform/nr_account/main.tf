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

# Get admin authentication domain
data "newrelic_authentication_domain" "admin_auth_domain" {
  name = var.admin_authentication_domain_name
}

# Get admin group
data "newrelic_group" "admin_group" {
  authentication_domain_id = data.newrelic_authentication_domain.admin_auth_domain.id
  name                     = var.admin_group_name
}

# Grant admin group access to the sub-account
resource "terraform_data" "admin_access_grant" {
  triggers_replace = {
    account_id = newrelic_account_management.subaccount.id
  }

  provisioner "local-exec" {
    command = "${path.module}/grant_access.sh '${var.newrelic_api_key}' '${upper(var.newrelic_region) == "US" ? "newrelic" : "eu.newrelic"}' '${data.newrelic_group.admin_group.id}' '${var.admin_role_name}' ${newrelic_account_management.subaccount.id}"
  }
}

# Get readonly authentication domain
data "newrelic_authentication_domain" "readonly_auth_domain" {
  name = var.readonly_authentication_domain_name
}

# Create read-only user
resource "newrelic_user" "readonly_user" {
  authentication_domain_id = data.newrelic_authentication_domain.readonly_auth_domain.id
  email_id                 = var.readonly_user_email
  name                     = var.readonly_user_name
  user_type                = "FULL_USER_TIER"
}

# Create readonly group
resource "newrelic_group" "readonly_group" {
  authentication_domain_id = data.newrelic_authentication_domain.readonly_auth_domain.id
  name                     = "${var.subaccount_name} - ReadOnly"
}

# Add user to readonly group
resource "newrelic_group_management" "readonly_group_membership" {
  authentication_domain_id = data.newrelic_authentication_domain.readonly_auth_domain.id
  group_id                 = newrelic_group.readonly_group.id
  user_ids                 = [newrelic_user.readonly_user.id]
}

# Grant readonly group access to the sub-account
resource "terraform_data" "readonly_access_grant" {
  triggers_replace = {
    account_id = newrelic_account_management.subaccount.id
    group_id   = newrelic_group.readonly_group.id
  }

  provisioner "local-exec" {
    command = "${path.module}/grant_access.sh '${var.newrelic_api_key}' '${upper(var.newrelic_region) == "US" ? "newrelic" : "eu.newrelic"}' '${newrelic_group.readonly_group.id}' '${var.readonly_role_name}' ${newrelic_account_management.subaccount.id}"
  }

  depends_on = [
    newrelic_group_management.readonly_group_membership
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
    terraform_data.admin_access_grant
  ]
}
