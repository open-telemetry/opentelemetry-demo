# Alerting Guide

This guide explains how to configure alerting for the OpenTelemetry Demo with Azure Data Explorer.

## Overview

The demo includes pre-configured Grafana alert rules that monitor your telemetry data using KQL queries against ADX. You can receive notifications via:

- **Email** (SMTP) - **Auto-provisioned via Terraform** using Azure Communication Services
- **Slack** - Incoming webhooks
- **Microsoft Teams** - Incoming webhooks
- **PagerDuty** - Integration key
- **Webhooks** - Any HTTP endpoint

## Quick Start: Email Alerts (Terraform)

When deploying with Terraform, Azure Communication Services is **automatically provisioned** for email alerts:

```bash
cd terraform

# Set your alert recipients
export TF_VAR_alert_recipients="team@company.com,oncall@company.com"

# Deploy infrastructure (includes Communication Services)
terraform apply
```

That's it! Terraform will:
1. Create Azure Communication Services resource
2. Create Email Communication Services with Azure-managed domain
3. Create Entra ID app for SMTP authentication
4. Configure Grafana SMTP settings automatically in `values-generated.yaml`

To disable email alerts, set:
```bash
export TF_VAR_enable_email_alerts=false
```

## Pre-configured Alert Rules

| Alert | Description | Default Threshold |
|-------|-------------|-------------------|
| **High Error Rate** | Triggers when error span percentage exceeds threshold | 5% |
| **High P95 Latency** | Triggers when P95 latency exceeds threshold | 500ms |
| **Service Down** | Triggers when expected services stop reporting | 5 min |
| **Error Logs Spike** | Triggers when error log count exceeds threshold | 10/5min |

## Configuration Methods

### Method 1: Helm Values (Recommended)

Configure notifications in your `values.yaml` or create a custom values file:

```yaml
grafana:
  alerting:
    enabled: true

    # Customize thresholds
    thresholds:
      errorRatePercent: 5
      p95LatencyMs: 500
      errorLogsCount: 10

    # Email notifications
    smtp:
      enabled: true
      host: "smtp.sendgrid.net"
      port: 587
      user: "apikey"
      password: "SG.xxxx"  # Your SendGrid API key
      fromAddress: "alerts@yourdomain.com"
      fromName: "Grafana Alerts"
      toAddresses: "team@yourdomain.com"

    # Slack notifications
    slack:
      enabled: true
      webhookUrl: "<YOUR_SLACK_WEBHOOK_URL>"
      channel: "#alerts"  # Optional

    # Microsoft Teams notifications
    teams:
      enabled: true
      webhookUrl: "https://outlook.office.com/webhook/xxx"
```

Deploy with your custom values:

```bash
helm upgrade otel-demo ./kubernetes/opentelemetry-demo-chart \
  -f ./kubernetes/opentelemetry-demo-chart/values-generated.yaml \
  -f ./my-alerting-values.yaml \
  -n otel-demo
```

### Method 2: Grafana UI (Self-Service)

Users can add additional notification channels directly in Grafana:

1. Access Grafana: `http://localhost:3000/grafana`
2. Navigate to **Alerting** → **Contact points**
3. Click **+ Add contact point**
4. Select integration type (Slack, Teams, Email, etc.)
5. Configure and save

## Setting Up Notification Channels

### Slack

1. Go to [Slack API: Incoming Webhooks](https://api.slack.com/messaging/webhooks)
2. Click **Create New App** → **From scratch**
3. Name your app and select workspace
4. Go to **Incoming Webhooks** → Enable
5. Click **Add New Webhook to Workspace**
6. Select channel and copy the webhook URL

```yaml
slack:
  enabled: true
  webhookUrl: "<YOUR_SLACK_WEBHOOK_URL>"
```

### Microsoft Teams

1. Open Teams and go to your channel
2. Click **•••** → **Connectors**
3. Find **Incoming Webhook** → **Configure**
4. Name the webhook and upload an icon (optional)
5. Click **Create** and copy the webhook URL

```yaml
teams:
  enabled: true
  webhookUrl: "https://outlook.office.com/webhook/xxx/IncomingWebhook/yyy/zzz"
```

### Email via SendGrid

1. Create a [SendGrid account](https://sendgrid.com/)
2. Go to **Settings** → **API Keys** → **Create API Key**
3. Select **Full Access** or **Restricted Access** with Mail Send permission
4. Copy the API key (shown only once!)

```yaml
smtp:
  enabled: true
  host: "smtp.sendgrid.net"
  port: 587
  user: "apikey"
  password: "SG.xxxxxxxxxx"
  fromAddress: "alerts@yourdomain.com"
  fromName: "OTel Demo Alerts"
  toAddresses: "team@company.com,oncall@company.com"
```

### Email via Azure Communication Services (Auto-Provisioned)

When using Terraform, Azure Communication Services is automatically provisioned. The following resources are created:

- **Azure Communication Services** - Core messaging resource
- **Email Communication Services** - Email capabilities
- **Azure Managed Domain** - Ready-to-use email domain (format: `xxxxxxxx.azurecomm.net`)
- **Entra ID Application** - For SMTP authentication

**Terraform automatically configures:**
```yaml
# Generated in values-generated.yaml
smtp:
  enabled: true
  host: "smtp.azurecomm.net"
  port: 587
  user: "<resource-name>.<entra-app-id>.<tenant-id>"
  password: "<entra-app-secret>"
  fromAddress: "DoNotReply@<guid>.azurecomm.net"
  fromName: "OTel Demo Alerts"
  toAddresses: "<your configured recipients>"
```

**Manual Setup (if not using Terraform):**

1. Create an Azure Communication Services resource
2. Go to **Email** → **Provision Domains**
3. Add an Azure managed domain or custom domain
4. Create an Entra ID app with Mail.Send permission
5. Configure the values above in your `values.yaml`

## Customizing Alert Rules

### Modify Thresholds

Update thresholds in your values file:

```yaml
grafana:
  alerting:
    thresholds:
      errorRatePercent: 2      # More sensitive to errors
      p95LatencyMs: 200        # Stricter latency SLO
      errorLogsCount: 5        # Fewer error logs allowed
```

### Add Custom Alert Rules via Grafana UI

1. Go to **Alerting** → **Alert rules**
2. Click **+ New alert rule**
3. Select **Azure Data Explorer** as data source
4. Write your KQL query:

```kql
// Example: Alert on specific service errors
OTelTraces
| where Timestamp > ago(5m)
| where ServiceName == "checkout"
| where StatusCode == "Error"
| summarize ErrorCount = count()
| where ErrorCount > 10
```

5. Configure thresholds and conditions
6. Set notification policy
7. Save

### Example Custom Alerts

**Checkout Service Latency:**
```kql
OTelTraces
| where Timestamp > ago(5m)
| where ServiceName == "checkout"
| where ParentSpanId == ""
| summarize P99 = percentile(Duration / 1000000.0, 99)
| where P99 > 1000
```

**Payment Failures:**
```kql
OTelTraces
| where Timestamp > ago(5m)
| where ServiceName == "payment"
| where StatusCode == "Error"
| summarize FailureCount = count()
| where FailureCount > 5
```

**High CPU Service:**
```kql
OTelMetrics
| where Timestamp > ago(5m)
| where Name == "process.cpu.utilization"
| summarize AvgCPU = avg(Value) by ServiceName
| where AvgCPU > 0.8
```

## Notification Policies

Control how alerts are routed to contact points:

1. Go to **Alerting** → **Notification policies**
2. Edit the default policy or add new ones
3. Configure:
   - **Group by**: Group related alerts together
   - **Group wait**: Wait time before sending first notification
   - **Group interval**: Interval between grouped notifications
   - **Repeat interval**: How often to re-notify for ongoing alerts

Example policy for critical alerts:
- Group wait: 10s (notify quickly)
- Repeat interval: 15m (frequent reminders)

Example policy for warnings:
- Group wait: 1m (batch notifications)
- Repeat interval: 4h (less frequent)

## Silencing Alerts

To temporarily silence alerts during maintenance:

1. Go to **Alerting** → **Silences**
2. Click **+ Create silence**
3. Add matchers (e.g., `alertname = High Error Rate`)
4. Set duration
5. Add comment explaining the silence

## Troubleshooting

### Alerts Not Firing

1. Check alert rule status in **Alerting** → **Alert rules**
2. Verify the KQL query returns data in **Explore**
3. Check Grafana logs: `kubectl logs -n otel-demo deployment/grafana`

### Notifications Not Sending

1. Verify contact point configuration in **Alerting** → **Contact points**
2. Click **Test** to send a test notification
3. Check SMTP settings if using email
4. Verify webhook URLs are accessible from the cluster

### SMTP Connection Issues

```bash
# Test SMTP connectivity from the cluster
kubectl run -it --rm smtp-test --image=busybox --restart=Never -- \
  nc -zv smtp.sendgrid.net 587
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Grafana Alerting                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │ Alert Rules │───▶│  Evaluation │───▶│   Router    │                  │
│  │   (KQL)     │    │   Engine    │    │  (Policies) │                  │
│  └─────────────┘    └─────────────┘    └──────┬──────┘                  │
│         │                                      │                         │
│         ▼                                      ▼                         │
│  ┌─────────────┐                    ┌─────────────────┐                 │
│  │     ADX     │                    │ Contact Points  │                 │
│  │  Database   │                    ├─────────────────┤                 │
│  └─────────────┘                    │ • Email (SMTP)  │────┐            │
│                                     │ • Slack         │    │            │
│                                     │ • Teams         │    │            │
│                                     │ • PagerDuty     │    │            │
│                                     │ • Webhooks      │    │            │
│                                     └─────────────────┘    │            │
│                                                            ▼            │
│                                     ┌─────────────────────────────────┐ │
│                                     │  Azure Communication Services   │ │
│                                     │  (Auto-provisioned by Terraform)│ │
│                                     │  • SMTP: smtp.azurecomm.net     │ │
│                                     │  • Azure Managed Domain         │ │
│                                     └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```
