# Coralogix Alerts as Code

This Terraform module defines all Coralogix alerts for the OTel Demo project. Each alert maps to a failure scenario from `trigger-incident.sh`.

## Prerequisites

1. **Coralogix API Key** - Get from Coralogix Settings → API Keys
2. **Terraform** >= 1.0
3. **Notification Group** - Create in Coralogix with incident.io integration

## Quick Start

```bash
# 1. Set environment variables
export CORALOGIX_API_KEY="your-api-key"
export CORALOGIX_ENV="US1"  # or EU2, AP1, etc.

# 2. Initialize Terraform
cd incidentfox/terraform/coralogix-alerts
terraform init

# 3. Preview changes
terraform plan -var="notification_group_id=your-notification-group-id"

# 4. Apply
terraform apply -var="notification_group_id=your-notification-group-id"
```

## Coralogix Environments

| Region | Environment Value |
|--------|-------------------|
| US (Ohio) | `US1` |
| US (Oregon) | `US2` |
| Europe | `EU1` |
| Europe 2 | `EU2` |
| India | `AP1` |
| Singapore | `AP2` |

## Alerts Included

### Tracing-based Alerts (7)

| Alert | Severity | Trigger Scenario |
|-------|----------|------------------|
| Payment Service Error Rate | Critical | `payment-failure` |
| Checkout Service Failures | Critical | Any upstream failure |
| Ad Service Latency Spike | Warning | `high-cpu` |
| Recommendation Service Latency | Warning | `cache-failure` |
| Product Catalog Error Rate | Critical | `catalog-failure` |
| Image Provider Slow Load | Info | `latency-spike` |
| Frontend Error Rate | Warning | Cascade from backend |

### Metric-based Alerts (6)

| Alert | Severity | Trigger Scenario |
|-------|----------|------------------|
| Ad Service High CPU | Warning | `high-cpu` |
| Email Service Memory Pressure | Warning | `memory-leak` |
| Kafka Consumer Lag | Warning | `kafka-lag` |
| OTel Demo Pod Restarts | Critical | Any crash |
| Frontend Traffic Spike | Info | `traffic-spike` |
| Payment Error Rate (Metric) | Critical | `payment-failure` |

## Scenario → Alert Mapping

```
trigger-incident.sh payment-failure
  └── Payment Service Error Rate (trace)
  └── Payment Error Rate (metric)
  └── Checkout Service Failures

trigger-incident.sh high-cpu
  └── Ad Service High CPU (metric)
  └── Ad Service Latency Spike (trace)

trigger-incident.sh cache-failure
  └── Recommendation Service Latency

trigger-incident.sh catalog-failure
  └── Product Catalog Error Rate
  └── Checkout Service Failures

trigger-incident.sh memory-leak
  └── Email Service Memory Pressure

trigger-incident.sh latency-spike
  └── Image Provider Slow Load

trigger-incident.sh kafka-lag
  └── Kafka Consumer Lag

trigger-incident.sh traffic-spike
  └── Frontend Traffic Spike
```

## Configuration

### Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `notification_group_id` | Coralogix notification group for incident.io | `""` |
| `environment` | Environment label (lab, staging, production) | `"lab"` |

### Example terraform.tfvars

```hcl
notification_group_id = "abc123-your-notification-group-id"
environment           = "lab"
```

## Testing

After applying the Terraform:

```bash
# 1. Trigger a payment failure
./incidentfox/scripts/trigger-incident.sh payment-failure

# 2. Wait 2-3 minutes for alert to fire

# 3. Check Coralogix → Alerts → Triggered Alerts

# 4. Verify incident.io received the alert

# 5. Clear the failure
./incidentfox/scripts/trigger-incident.sh clear-all
```

## Customizing Thresholds

If alerts fire during normal operation, increase thresholds:

```hcl
# In alerts.tf, modify the condition block:
condition {
  condition_type = "more_than"
  threshold      = 10  # Increase from 5
  timeframe      = "10_min"  # Increase from 5_min
}
```

## Importing Existing Alerts

If you created alerts manually in the UI:

```bash
terraform import coralogix_alert.payment_error_rate "alert-id-from-coralogix"
```

## Destroying Alerts

```bash
terraform destroy -var="notification_group_id=your-id"
```

## Troubleshooting

### "Provider not found"

```bash
terraform init -upgrade
```

### "Invalid API key"

Verify your environment variables:
```bash
echo $CORALOGIX_API_KEY
echo $CORALOGIX_ENV
```

### Alerts not firing

1. Check telemetry is flowing: Coralogix → Explore → filter by service
2. Verify failure injection: `kubectl -n otel-demo logs deployment/payment`
3. Check alert is enabled: Coralogix → Alerts → find alert → verify "Enabled"

