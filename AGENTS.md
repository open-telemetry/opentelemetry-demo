# AI Agent Context: AWS Playground / IncidentFox Demo

> **Purpose**: This document provides context for AI agents (Cursor, Claude Code, etc.) working on this repository. It captures institutional knowledge about the architecture, setup, and common operations.

## Quick Reference

| What | Command/Location |
|------|------------------|
| Check active failures | `./incidentfox/scripts/trigger-incident.sh --status --kube` |
| Trigger payment failure | `./incidentfox/scripts/trigger-incident.sh service-failure 50% --kube` |
| Clear all failures | `./incidentfox/scripts/trigger-incident.sh clear-all --kube` |
| Check EKS pods | `kubectl -n otel-demo get pods` |
| Check flagd config | `kubectl get configmap flagd-config -n otel-demo -o jsonpath='{.data.demo\.flagd\.json}' \| jq .` |

---

## 1. Project Overview

This repository contains:
1. **OpenTelemetry Demo** - A microservices e-commerce application instrumented with OpenTelemetry
2. **IncidentFox** - Scripts and configuration for failure injection, alerting, and incident management demos
3. **Infrastructure** - Terraform/EKS configuration for AWS deployment

### Key Directories

```
aws-playground/
├── src/                          # OpenTelemetry Demo source code
│   ├── payment/                  # Node.js payment service (key for failure injection)
│   ├── flagd/demo.flagd.json     # Feature flag definitions (LOCAL - not used on EKS)
│   ├── otel-collector/           # OTel Collector configuration
│   └── [other services]/
├── incidentfox/
│   ├── scripts/
│   │   ├── trigger-incident.sh   # Master script for failure injection
│   │   ├── trigger_incidentio_incident.sh  # Direct incident.io API caller
│   │   └── scenarios/            # Individual failure scenario scripts
│   ├── docs/
│   │   └── coralogix-alerts.md   # Alert definitions documentation
│   └── terraform/
│       └── coralogix-alerts/     # Terraform for Coralogix alerts (incomplete)
└── AGENTS.md                     # This file
```

---

## 2. Deployment Architecture

### Production Environment: AWS EKS

The demo runs on **AWS EKS** in `us-west-2`:
- **Cluster name**: `incidentfox-demo`
- **Namespace**: `otel-demo`
- **Node type**: `t3.medium` (3-4 nodes)

### Key Services

| Service | Purpose | Notes |
|---------|---------|-------|
| `payment` | Payment processing | Primary target for failure injection |
| `checkout` | Order checkout flow | Calls payment, shipping, email |
| `flagd` | Feature flag server | Controls failure injection |
| `otel-collector` | Telemetry aggregation | Forwards to Coralogix (OpenSearch removed) |
| `traffic-generator` | Traffic generation | Simple curl-based, stable |
| `frontend` | Web UI | Accessible via LoadBalancer |

### Scaled Down / Disabled Services

| Service | Reason |
|---------|--------|
| `load-generator` | Crashes due to Python/gevent bug - replaced by `traffic-generator` |
| `opensearch` | Not needed - using Coralogix for logs |

### Telemetry Flow

```
Services → OTel Collector (otel-demo namespace)
                ↓
         Coralogix OTel Integration (coralogix namespace)
                ↓
         Coralogix Cloud (logs, traces, metrics)
                ↓
         Coralogix Alerts → incident.io API → Slack
```

---

## 3. Feature Flags & Failure Injection

### How It Works

1. **flagd** runs as a deployment in `otel-demo` namespace
2. Configuration is stored in ConfigMap `flagd-config`
3. Services query flagd at runtime to check flag values
4. Setting a flag to a non-"off" value triggers the corresponding failure

### Available Failure Scenarios

| Scenario | Flag Name | Effect |
|----------|-----------|--------|
| `service-failure` | `paymentFailure` | Payment fails n% of the time |
| `high-cpu` | `adHighCpu` | Ad service consumes high CPU |
| `memory-leak` | `emailMemoryLeak` | Email service leaks memory |
| `cache-failure` | `recommendationCacheFailure` | Recommendation cache misses |
| `kafka-lag` | `kafkaQueueProblems` | Kafka consumer lag |
| `latency-spike` | `imageSlowLoad` | Slow image loading |
| `catalog-failure` | `productCatalogFailure` | Product catalog errors |
| `traffic-spike` | `loadGeneratorFloodHomepage` | Traffic flood |

### Using the Trigger Script

```bash
# Check current status
./incidentfox/scripts/trigger-incident.sh --status --kube

# Trigger a failure (on Kubernetes)
./incidentfox/scripts/trigger-incident.sh service-failure 50% --kube

# Trigger failure + create incident.io alert after 3 minutes
./incidentfox/scripts/trigger-incident.sh service-failure --kube --incidentio

# Clear all failures
./incidentfox/scripts/trigger-incident.sh clear-all --kube
```

### IMPORTANT: Local vs Kubernetes

- The `src/flagd/demo.flagd.json` file is for **LOCAL development only**
- On EKS, flags are stored in the **ConfigMap** `flagd-config`
- Always use `--kube` flag when working with the EKS deployment
- After changing flags, flagd deployment is automatically restarted
- **Payment service may need restart** to reconnect to flagd

---

## 4. Coralogix Integration

### Setup

- **Coralogix Environment**: US1
- **Integration Method**: Coralogix OTel Integration Helm chart in `coralogix` namespace
- **Data Types**: Logs, Traces, Metrics

### How Telemetry Flows

1. Demo services emit telemetry to OTel Collector in `otel-demo` namespace
2. OTel Collector forwards to Coralogix collector via OTLP
3. Coralogix collector sends to Coralogix cloud

**Note**: The Coralogix DaemonSet agents are configured to **exclude** logs from the `otel-demo` namespace to avoid duplicate/fragmented logs (since otel-demo services already emit via OTLP).

### Viewing Data in Coralogix

- **Traces**: APM → Tracing → Filter by service name (e.g., "payment")
- **Logs**: Explore → Logs → Filter by subsystem
- **Metrics**: Explore → Metrics

### Log Collection Configuration

- **otel-demo namespace**: Logs collected via OTLP only (DaemonSet excluded)
- **Other namespaces**: Logs collected via DaemonSet file scraping

**Note**: Application logs may appear under `opentelemetry-demo` as the application name in Coralogix.

---

## 5. incident.io Integration

### API Access

```bash
# API Key (has create incidents permission)
INCIDENTIO_API_KEY="<your-incident-io-api-key>"  # Set via environment variable

# Severity IDs
SEVERITY_MINOR="01KCSZ7E54DSD4TTVPXFEEQ2PV"
SEVERITY_MAJOR="01KCSZ7E54R7NQE5570YHFA3C8"
SEVERITY_CRITICAL="01KCSZ7E54WJQBBZ0HBYQ152FW"
```

### Creating Incidents via API

```bash
curl -X POST "https://api.incident.io/v2/incidents" \
  -H "Authorization: Bearer $INCIDENTIO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Payment Service - High Error Rate",
    "idempotency_key": "unique-key-123",
    "severity_id": "01KCSZ7E54WJQBBZ0HBYQ152FW",
    "visibility": "public",
    "summary": "Payment errors detected"
  }'
```

### Using the Script

```bash
./incidentfox/scripts/trigger_incidentio_incident.sh "Incident Name" "Summary" "critical|major|minor"
```

### Coralogix → incident.io Webhook

**Status**: Not fully working. Coralogix Generic Webhook only supports HTTP, but incident.io requires HTTPS.

**Workaround**: Use the `--incidentio` flag with `trigger-incident.sh` to create incidents after a delay:
```bash
./incidentfox/scripts/trigger-incident.sh service-failure --kube --incidentio --incidentio-delay 180
```

---

## 6. Common Troubleshooting

### Traffic Generator

The original `load-generator` has been **scaled to 0** due to a Python/gevent bug that caused constant crashes.

We now use `traffic-generator` - a simple pod running curl loops that generates continuous traffic including checkout flows.

```bash
# Check traffic generator status
kubectl -n otel-demo get pods | grep traffic

# Verify traffic is flowing (look for recent payment logs)
kubectl -n otel-demo logs deployment/payment --tail=5
```

If traffic stops flowing, restart the traffic-generator:
```bash
kubectl -n otel-demo delete pod traffic-generator
# It will be recreated automatically
```

### Feature Flag Not Taking Effect

**Symptom**: Changed flag via script but service behavior doesn't change

**Fix**:
1. Verify ConfigMap was updated:
   ```bash
   kubectl get configmap flagd-config -n otel-demo -o jsonpath='{.data.demo\.flagd\.json}' | jq '.flags.paymentFailure.defaultVariant'
   ```
2. Check flagd pod is running the latest config:
   ```bash
   kubectl -n otel-demo delete pod -l app.kubernetes.io/name=flagd
   ```
3. Restart the affected service:
   ```bash
   kubectl -n otel-demo rollout restart deployment/payment
   ```
4. Test flagd directly:
   ```bash
   kubectl -n otel-demo port-forward svc/flagd 8016:8016 &
   curl -s http://localhost:8016/ofrep/v1/evaluate/flags/paymentFailure -X POST -H "Content-Type: application/json" -d '{}' | jq .
   ```

### Pods Stuck in Pending/Init

**Symptom**: Pods won't start, show "Insufficient memory" or "Too many pods"

**Fix**: The cluster may be resource-constrained. Scale down non-essential services:
```bash
kubectl -n otel-demo scale deployment opensearch --replicas=0
kubectl -n otel-demo scale deployment jaeger --replicas=0
```

### No Traces Appearing in Coralogix

**Check**:
1. Is the OTel Collector running?
   ```bash
   kubectl -n otel-demo get pods | grep otel-collector
   ```
2. Is the Coralogix integration running?
   ```bash
   kubectl -n coralogix get pods
   ```
3. Check collector logs for errors:
   ```bash
   kubectl -n otel-demo logs deployment/otel-collector --tail=50 | grep -i error
   ```

---

## 7. Useful kubectl Commands

```bash
# Get all pods in demo namespace
kubectl -n otel-demo get pods

# Check pod logs
kubectl -n otel-demo logs deployment/payment --tail=50

# Follow logs in real-time
kubectl -n otel-demo logs -f deployment/payment

# Restart a deployment
kubectl -n otel-demo rollout restart deployment/payment

# Scale a deployment
kubectl -n otel-demo scale deployment/opensearch --replicas=0

# Port forward to a service
kubectl -n otel-demo port-forward svc/frontend 8080:8080

# Get ConfigMap contents
kubectl get configmap flagd-config -n otel-demo -o yaml

# Patch ConfigMap
kubectl patch configmap flagd-config -n otel-demo --type merge -p '{"data":{"key":"value"}}'
```

---

## 8. Service Dependencies

For a complete service dependency diagram and detailed documentation, see:
📄 **[incidentfox/docs/service-dependencies.md](incidentfox/docs/service-dependencies.md)**

### Quick Reference

```
Frontend
    ↓
Checkout ──→ Payment (failure injection target)
    │
    ├──→ Shipping ──→ Quote
    ├──→ Email
    ├──→ Currency
    ├──→ Cart ──→ Valkey/Redis
    └──→ Kafka ──→ Accounting ──→ PostgreSQL
                └──→ Fraud Detection

Product Catalog ←── Frontend, Checkout, Recommendation
Recommendation ←── Frontend (cache failure target)
Ad Service ←── Frontend (CPU/GC pressure target)
flagd ←── Payment, Ad, Recommendation, Email (feature flags)
```

---

## 9. Files Changed Frequently

| File | Purpose | Notes |
|------|---------|-------|
| `incidentfox/scripts/trigger-incident.sh` | Master failure injection script | Supports `--kube` and `--incidentio` flags |
| `src/flagd/demo.flagd.json` | Local flag config | **Not used on EKS** |
| ConfigMap `flagd-config` | EKS flag config | Modified by trigger-incident.sh |

---

## 10. Known Limitations

1. **Coralogix → incident.io webhook**: Doesn't work because Coralogix Generic Webhook is HTTP-only. Use `--incidentio` flag instead.
2. **Log subsystem attribution**: Logs may appear under `otel-collector` subsystem instead of service name
3. **OTel collector self-metrics warning**: Minor log noise about HTTPS/HTTP mismatch for self-telemetry (doesn't affect operation)
4. **Terraform alerts**: The Coralogix Terraform provider code exists but wasn't fully deployed

---

## 11. Quick Health Check

Run this to verify the system is working:

```bash
# 1. Check all pods are running
kubectl -n otel-demo get pods | grep -v Running

# 2. Check no active failures
./incidentfox/scripts/trigger-incident.sh --status --kube

# 3. Check traffic is flowing
kubectl -n otel-demo logs deployment/payment --tail=5

# 4. Check flagd is responsive
kubectl -n otel-demo port-forward svc/flagd 8016:8016 &
sleep 2
curl -s http://localhost:8016/ofrep/v1/evaluate/flags/paymentFailure -X POST -d '{}' | jq .variant
pkill -f "port-forward.*flagd"
```

---

## 12. Last Verified Status (January 9, 2026)

| Component | Status | Notes |
|-----------|--------|-------|
| All 24 services | ✅ Running | No crashloops |
| Traffic flow | ✅ Working | 250+ transactions/5sec |
| Payment service | ✅ Working | Processing orders |
| Checkout flow | ✅ Working | End-to-end tested |
| Feature flags (flagd) | ✅ Working | All flags off |
| Coralogix integration | ✅ Working | Logs, traces, metrics flowing |
| OTel Collector | ✅ Working | Forwarding to Coralogix |
| traffic-generator | ✅ Running | Generating continuous traffic |
| load-generator | ⏸️ Scaled to 0 | Replaced by traffic-generator |
| OpenSearch | ⏸️ Disabled | Removed from pipeline, using Coralogix |

---

*Last updated: January 9, 2026*
*Verified by: AI Agent health check*
*Session context: Coralogix + incident.io integration, failure injection, telemetry optimization*

