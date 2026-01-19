# New Relic Account Management Module

This Terraform module creates a New Relic sub-account and generates a license key for the OpenTelemetry Demo.

## Purpose

Use this module to:
1. Create a dedicated New Relic sub-account for the OpenTelemetry Demo
2. Generate a license key for data ingestion
3. Get credentials ready for the `install-k8s.sh` script

## Prerequisites

- Terraform >= 1.0
- New Relic account with sub-account creation permissions
- New Relic User API Key

## Usage

Navigate to this directory and apply directly:

```bash
cd newrelic/terraform/account_management

# Set Terraform variables (all provider config via TF_VAR_*)
export TF_VAR_newrelic_api_key="your-user-api-key"
export TF_VAR_newrelic_parent_account_id="your-parent-account-id"
export TF_VAR_newrelic_region="US"  # or "EU" (optional, defaults to "US")
export TF_VAR_subaccount_name="OpenTelemetry Demo Environment"

# Initialize and apply
terraform init
terraform apply
```

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| newrelic_api_key | New Relic User API Key | `string` | n/a | yes |
| newrelic_parent_account_id | Parent account ID for creating sub-accounts | `string` | n/a | yes |
| newrelic_region | New Relic region (US or EU) | `string` | `"US"` | no |
| subaccount_name | Name of the sub-account to create | `string` | n/a | yes |

Set variables using environment variables (recommended):
- `TF_VAR_newrelic_api_key` - Your User API Key
- `TF_VAR_newrelic_parent_account_id` - Your parent account ID
- `TF_VAR_newrelic_region` - Region (US or EU, defaults to US)
- `TF_VAR_subaccount_name` - Name for the sub-account

Or use a `.tfvars` file:

```hcl
# terraform.tfvars
newrelic_api_key           = "your-api-key"
newrelic_parent_account_id = "1234567"
newrelic_region            = "US"
subaccount_name            = "OpenTelemetry Demo Environment"
```

## Outputs

| Name | Description | Sensitive |
|------|-------------|:---------:|
| account_id | The ID of the created sub-account | no |
| account_name | The name of the created sub-account | no |
| license_key | The license key for data ingestion | yes |
| region | The region where the sub-account was created | no |

## Complete Workflow

### Step 1: Set Environment Variables

```bash
cd newrelic/terraform/account_management

# Set all configuration via TF_VAR_* (consistent!)
export TF_VAR_newrelic_api_key="your-user-api-key"
export TF_VAR_newrelic_parent_account_id="your-parent-account-id"
export TF_VAR_newrelic_region="US"
export TF_VAR_subaccount_name="OpenTelemetry Demo"
```

### Step 2: Apply Terraform

```bash
terraform init
terraform apply
```

### Step 3: Export License Key

```bash
export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)
```

## Notes

- The license key is created with `INGEST` type and `LICENSE` ingest type
- The sub-account is created in your specified region (US or EU)
- You need admin-level permissions in your parent account to create sub-accounts
- The license key output is marked as sensitive, retrieve it with: `terraform output -raw license_key`
