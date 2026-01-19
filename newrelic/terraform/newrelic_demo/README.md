# New Relic Demo Module

This Terraform module creates New Relic resources for the OpenTelemetry Demo.

## Prerequisites

- The OpenTelemetry Demo must be deployed and reporting data to New Relic
- New Relic User API Key
- Account ID where the demo is deployed

## Usage

Navigate to this directory and apply directly:

```bash
cd newrelic/terraform/newrelic_demo

# Set required environment variables
export NEW_RELIC_API_KEY="your-user-api-key"
export NEW_RELIC_REGION="US"  # or "EU"

# Set Terraform variables
export TF_VAR_account_id="1234567"  # Your New Relic account ID
export TF_VAR_checkout_service_name="checkout"  # Optional, defaults to "checkout"

# Initialize and apply
terraform init
terraform apply
```

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| account_id | The New Relic account ID where the demo is deployed | `string` | n/a | yes |
| checkout_service_name | Name of the checkout service entity | `string` | `"checkout"` | no |

Set variables using environment variables:
- `TF_VAR_account_id` - Your New Relic account ID
- `TF_VAR_checkout_service_name` - Service name (optional)

Or use a `.tfvars` file:

```hcl
# terraform.tfvars
account_id            = "1234567"
checkout_service_name = "checkout"
```

## Troubleshooting

### "Entity not found" error

If you get an error that the entity cannot be found:

1. Verify the demo is deployed and running:
   ```bash
   kubectl get pods -n opentelemetry-demo
   ```

2. Check if the checkout service is reporting to New Relic:
   - Go to New Relic UI → All Entities → Services - OpenTelemetry
   - Look for "checkout"

3. Wait longer - it can take 2-5 minutes for data to appear

4. Verify you're using the correct account ID:
   ```bash
   # If using account_management module
   cd ../account_management
   terraform output account_id
   ```

### Different service name

If your checkout service has a different name in New Relic, set the variable:

```bash
export TF_VAR_checkout_service_name="your-service-name"
terraform apply
```
