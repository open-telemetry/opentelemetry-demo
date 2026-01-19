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

# Set required environment variables
export NEW_RELIC_API_KEY="your-user-api-key"
export NEW_RELIC_ACCOUNT_ID="your-parent-account-id"
export NEW_RELIC_REGION="US"  # or "EU"

# Set Terraform variables
export TF_VAR_subaccount_name="OpenTelemetry Demo Environment"
export TF_VAR_region="us"  # or "eu" (optional, defaults to "us")

# Initialize and apply
terraform init
terraform apply
```

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| subaccount_name | Name of the New Relic sub-account to create | `string` | n/a | yes |
| region | Region for the sub-account (us or eu) | `string` | `"us"` | no |

Set variables using environment variables:
- `TF_VAR_subaccount_name` - Name for the sub-account
- `TF_VAR_region` - Region (us or eu)

Or use a `.tfvars` file:

```hcl
# terraform.tfvars
subaccount_name = "OpenTelemetry Demo Environment"
region          = "us"
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

# New Relic provider configuration
export NEW_RELIC_API_KEY="your-user-api-key"
export NEW_RELIC_ACCOUNT_ID="your-parent-account-id"
export NEW_RELIC_REGION="US"

# Terraform variables
export TF_VAR_subaccount_name="OpenTelemetry Demo"
export TF_VAR_region="us"
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
