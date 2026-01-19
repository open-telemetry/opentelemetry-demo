# New Relic OpenTelemetry Demo Terraform Modules

Terraform modules to automate New Relic setup for the OpenTelemetry Demo.

## Overview

This directory contains two independent Terraform modules:

1. **`account_management`** - Creates a New Relic sub-account and license key
2. **`newrelic_demo`** - Creates an SLO for the checkout service (automatically finds the entity)

## Quick Start

### Step 1: Create Sub-Account and License Key

```bash
cd newrelic/terraform/account_management

# Set all configuration via TF_VAR_* (consistent!)
export TF_VAR_newrelic_api_key="your-user-api-key"
export TF_VAR_newrelic_parent_account_id="your-parent-account-id"
export TF_VAR_newrelic_region="US"  # Used for both provider and sub-account
export TF_VAR_subaccount_name="OpenTelemetry Demo"

# Create sub-account
terraform init
terraform apply

# Export license key
export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)
```

### Step 2: Deploy OpenTelemetry Demo

```bash
cd ../../scripts
./install-k8s.sh
```

### Step 3: Wait for Data

Wait 2-5 minutes for the demo to start reporting data to New Relic.

```bash
# Check pod status
kubectl get pods -n opentelemetry-demo

# Verify in New Relic UI:
# Go to "All Entities" → "Services - OpenTelemetry" → Look for "checkout"
```

### Step 4: Create SLO

```bash
cd ../terraform/newrelic_demo

# Set variables (reuse API key from before)
export TF_VAR_newrelic_api_key="your-api-key"  # Same as Step 1
export TF_VAR_account_id=$(cd ../account_management && terraform output -raw account_id)

# Create SLO
terraform init
terraform apply
```

## Module Details

### account_management

Creates a New Relic sub-account and generates an ingest license key.

**Usage:** Navigate to `account_management/` and run `terraform apply` directly.

**Variables (set via TF_VAR_*):**
- `newrelic_api_key` (required) - New Relic User API Key
- `newrelic_parent_account_id` (required) - Parent account ID
- `newrelic_region` (optional) - Region: "US" or "EU" (default: "US")
- `subaccount_name` (required) - Name for the sub-account

**Outputs:**
- `account_id` - The created account ID
- `license_key` - The ingest license key (sensitive)
- `account_name` - The account name
- `region` - The account region

[Full documentation](./account_management/README.md)

### newrelic_demo

Automatically finds the checkout service and creates an SLO.

**Usage:** Navigate to `newrelic_demo/` and run `terraform apply` directly.

**Variables (set via TF_VAR_*):**
- `newrelic_api_key` (required) - New Relic User API Key
- `newrelic_region` (optional) - Region: "US" or "EU" (default: "US")
- `account_id` (required) - New Relic account ID where demo is deployed
- `checkout_service_name` (optional) - Service name (default: "checkout")

**Outputs:**
- `checkout_service_guid` - The found entity GUID
- `checkout_service_name` - The service name
- `slo_id` - The created SLO ID
- `slo_name` - The SLO name

**SLO Configuration:**
- Target: 99.5% availability
- Time Window: 1-day rolling
- Metric: Server-side spans without errors

[Full documentation](./newrelic_demo/README.md)

## Usage Patterns

### Pattern 1: Direct Module Usage (Recommended)

Navigate to each module directory and apply directly using `TF_VAR_*` environment variables:

```bash
# Step 1: Create account
cd account_management
export TF_VAR_newrelic_api_key="your-api-key"
export TF_VAR_newrelic_parent_account_id="your-parent-account-id"
export TF_VAR_newrelic_region="US"
export TF_VAR_subaccount_name="OpenTelemetry Demo"
terraform init && terraform apply

# Step 2: Deploy demo
export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)
cd ../../scripts && ./install-k8s.sh

# Step 3: Wait 2-5 minutes

# Step 4: Create SLO
cd ../terraform/newrelic_demo
export TF_VAR_newrelic_api_key="your-api-key"  # Same as Step 1
export TF_VAR_account_id=$(cd ../account_management && terraform output -raw account_id)
terraform init && terraform apply
```

This is the simplest approach - no extra configuration files needed.

### Pattern 2: Using Terraform Variables Files

Create a `terraform.tfvars` file instead of using environment variables:

```bash
cd account_management

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
newrelic_api_key           = "your-api-key"
newrelic_parent_account_id = "your-parent-account-id"
newrelic_region            = "US"
subaccount_name            = "OpenTelemetry Demo"
EOF

terraform init && terraform apply
```

### Pattern 3: Using Existing Account

If you already have a New Relic account and license key:

```bash
# Deploy demo with existing key
export NEW_RELIC_LICENSE_KEY="your-existing-key"
cd scripts
./install-k8s.sh

# Wait 2-5 minutes

# Create SLO
cd ../terraform/newrelic_demo
export TF_VAR_newrelic_api_key="your-api-key"
export TF_VAR_account_id="your-account-id"
terraform init && terraform apply
```

## Prerequisites

- Terraform >= 1.0
- New Relic account
- New Relic User API Key
- Kubernetes cluster (for demo deployment)
- `kubectl` and `helm` (for demo deployment)

## Authentication

Both modules use the New Relic Terraform provider and require:

```bash
export NEW_RELIC_API_KEY="your-user-api-key"
export NEW_RELIC_REGION="US"  # or "EU"

# For account_management only:
export NEW_RELIC_ACCOUNT_ID="your-parent-account-id"
```

Get your User API Key:
1. Go to [New Relic API Keys](https://one.newrelic.com/launcher/api-keys-ui.api-keys-launcher)
2. Create a User key with appropriate permissions

## Setting Variables

Terraform variables can be set in multiple ways:

1. **Environment Variables (TF_VAR_*)** - Recommended for credentials and dynamic values:
   ```bash
   export TF_VAR_subaccount_name="My Account"
   export TF_VAR_account_id="1234567"
   ```

2. **terraform.tfvars File** - Good for static configuration:
   ```hcl
   subaccount_name = "OpenTelemetry Demo"
   region          = "us"
   ```

3. **Command Line Flags**:
   ```bash
   terraform apply -var="subaccount_name=My Account"
   ```

## Troubleshooting

### "Entity not found" when creating SLO

The checkout service isn't reporting to New Relic yet:
- Wait longer (2-5 minutes after deployment)
- Verify pods are running: `kubectl get pods -n opentelemetry-demo`
- Check New Relic UI for the service

### "Permission denied" when creating sub-account

You need admin permissions in the parent account:
- Verify your User API Key has correct permissions
- Check you've set `NEW_RELIC_ACCOUNT_ID` correctly
- Ensure your account can create sub-accounts

### License key not working

- Ensure you exported it correctly: `export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)`
- Verify the key was created: `terraform output license_key`
- Check you're using the correct account ID

## Cleanup

Remove all resources:

```bash
# Remove SLO
cd terraform/newrelic_demo
terraform destroy

# Uninstall demo
cd ../../scripts
./cleanup-k8s.sh

# Remove account (WARNING: Deletes all data in sub-account)
cd ../terraform/account_management
terraform destroy
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Workflow                                            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. account_management module                      │
│     ├─ Creates New Relic sub-account               │
│     └─ Generates license key                       │
│                                                     │
│  2. install-k8s.sh script                          │
│     ├─ Deploys OpenTelemetry Demo                  │
│     └─ Services report to New Relic                │
│                                                     │
│  3. Wait 2-5 minutes                               │
│     └─ Checkout service appears in New Relic       │
│                                                     │
│  4. newrelic_demo module                           │
│     ├─ Finds checkout service (via data source)    │
│     └─ Creates SLO                                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Benefits

- **Direct usage**: Simply `cd` into a module directory and run `terraform apply`
- **No manual GUID lookup**: The `newrelic_demo` module automatically finds entities
- **Flexible variable setting**: Use TF_VAR_* environment variables, .tfvars files, or command-line flags
- **Clean separation**: Create accounts and SLOs independently
- **Simple workflow**: Clear step-by-step process with no complex configuration
- **No conditionals**: Each module has one clear purpose

## Contributing

When modifying these modules:
- Keep modules independent and directly usable (no wrapper configs needed)
- Test direct usage with TF_VAR_* environment variables
- Document any new variables with examples
- Update this README with architectural changes
