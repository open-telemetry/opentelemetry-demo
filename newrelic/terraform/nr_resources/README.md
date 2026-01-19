# New Relic Resources Module

This Terraform module creates New Relic resources to showcase New Relic capabilities with the OpenTelemetry Demo.

## Purpose

This module demonstrates various New Relic features and capabilities including:
- **Service Level Objectives (SLOs)** - Currently creates an SLO for the checkout service
- **Future additions** - Alerts, dashboards, teams, scorecards, and other resources to showcase New Relic's observability platform

## Prerequisites

- The OpenTelemetry Demo must be deployed and reporting data to New Relic
- New Relic User API Key
- Account ID where the demo is deployed

## Usage

Navigate to this directory and apply directly:

```bash
cd newrelic/terraform/nr_resources

# Set Terraform variables (all provider config via TF_VAR_*)
export TF_VAR_newrelic_api_key="your-user-api-key"
export TF_VAR_newrelic_region="US"  # or "EU" (optional, defaults to "US")
export TF_VAR_account_id="1234567"  # Your New Relic account ID
export TF_VAR_checkout_service_name="checkout"  # Optional, defaults to "checkout"

# Initialize and apply
terraform init
terraform apply
```

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| newrelic_api_key | New Relic User API Key | `string` | n/a | yes |
| newrelic_region | New Relic region (US or EU) | `string` | `"US"` | no |
| account_id | The New Relic account ID where the demo is deployed | `string` | n/a | yes |
| checkout_service_name | Name of the checkout service entity | `string` | `"checkout"` | no |

Set variables using environment variables (recommended):
- `TF_VAR_newrelic_api_key` - Your User API Key
- `TF_VAR_newrelic_region` - Region (US or EU, defaults to US)
- `TF_VAR_account_id` - Your New Relic account ID
- `TF_VAR_checkout_service_name` - Service name (optional)

Or use a `.tfvars` file:

```hcl
# terraform.tfvars
newrelic_api_key      = "your-api-key"
newrelic_region       = "US"
account_id            = "1234567"
checkout_service_name = "checkout"
```

## What Gets Created

### Service Level Objectives (SLOs)

Currently, this module creates an SLO for the checkout service with:
- **Target**: 99.5% availability
- **Time Window**: 1-day rolling window
- **Metric**: Server-side spans without errors

### Future Resources

This module will be expanded to include additional New Relic resources such as:
- Alert policies and conditions
- Custom dashboards
- Teams and user management
- Service scorecards
- Synthetic monitors
- And more...

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
   # If using nr_account module
   cd ../nr_account
   terraform output account_id
   ```

### Different service name

If your checkout service has a different name in New Relic, set the variable:

```bash
export TF_VAR_checkout_service_name="your-service-name"
terraform apply
```
