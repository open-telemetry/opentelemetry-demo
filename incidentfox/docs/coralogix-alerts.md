# Coralogix Alert Definitions for Controlled Failures

This document defines Coralogix alerts that **stay silent during normal operation** but **fire when you inject failures** via `./incidentfox/scripts/trigger-incident.sh`.

## Alert Design Principles

1. **Normal baseline = no alerts**: Thresholds are set above normal operating values
2. **Failure injection = immediate detection**: Each scenario produces clear, detectable signals
3. **Map to incident.io**: All alerts route to your incident.io webhook

---

## Quick Reference: Scenario → Alert Mapping

| Scenario | Trigger Command | Primary Alert | Secondary Alert |
|----------|-----------------|---------------|-----------------|
| `high-cpu` | `./trigger-incident.sh high-cpu` | Ad Service High CPU | Ad Service Latency |
| `payment-failure` | `./trigger-incident.sh service-failure` | Payment Error Rate | Checkout Failures |
| `payment-unreachable` | `./trigger-incident.sh service-unreachable` | Payment Unreachable | Checkout Errors |
| `cache-failure` | `./trigger-incident.sh cache-failure` | Recommendation Latency | Cache Miss Rate |
| `catalog-failure` | `./trigger-incident.sh catalog-failure` | Product Catalog Errors | Multiple Service Errors |
| `kafka-lag` | `./trigger-incident.sh kafka-lag` | Kafka Consumer Lag | Order Processing Delay |
| `memory-leak` | `./trigger-incident.sh memory-leak` | Email Service Memory | Email OOM Errors |
| `latency-spike` | `./trigger-incident.sh latency-spike` | Image Provider Latency | Frontend Slow Load |
| `traffic-spike` | `./trigger-incident.sh traffic-spike` | Request Rate Spike | Error Rate Increase |

---

## Alert Definitions

### 1. Payment Error Rate (Critical)

**Triggers on:** `paymentFailure` feature flag (any percentage)

**Type:** Metric - Threshold

**Query:**
```
sum(rate(traces_spanmetrics_calls_total{service_name="payment", status_code="STATUS_CODE_ERROR"}[5m])) 
/ 
sum(rate(traces_spanmetrics_calls_total{service_name="payment"}[5m])) 
* 100
```

**Coralogix Setup:**
- **Alert Type:** Metric - Threshold
- **Metric:** Error rate derived from traces or `app.payment.transactions` with error status
- **Condition:** `> 5%` over 2 minutes
- **Normal baseline:** ~0% (payments always succeed)
- **During failure:** 10-100% depending on flag setting

**Alternative (Logs-based):**
- **Alert Type:** Logs - Threshold
- **Query:** `service.name:"payment" AND level:"error" AND "Payment request failed"`
- **Condition:** `> 3 occurrences` in 2 minutes
- **Normal baseline:** 0 occurrences

**Priority:** P1 (Critical)

---

### 2. Ad Service High CPU (High)

**Triggers on:** `adHighCpu` feature flag

**Type:** Metric - Threshold

**Query (Infrastructure metrics):**
```
avg(container_cpu_usage_seconds_total{container="ad"}) by (pod) * 100
```

**Coralogix Setup:**
- **Alert Type:** Metric - Threshold  
- **Metric:** `container.cpu.usage` or `process.runtime.jvm.cpu.utilization`
- **Filter:** `service.name = "ad"` or `k8s.container.name = "ad"`
- **Condition:** `> 70%` sustained for 1 minute
- **Normal baseline:** 5-15%
- **During failure:** 80-100%

**Alternative (Logs-based detection):**
- **Alert Type:** Logs - Immediate
- **Query:** `service.name:"ad" AND "High CPU-Load problempattern enabled"`
- **Condition:** Any occurrence
- **Normal baseline:** Never appears

**Priority:** P2 (High)

---

### 3. Ad Service Latency Spike (High)

**Triggers on:** `adHighCpu` feature flag (secondary effect)

**Type:** Tracing - Threshold

**Coralogix Setup:**
- **Alert Type:** Tracing - Threshold
- **Service:** `ad`
- **Operation:** `getAds` or `*`
- **Metric:** P95 latency
- **Condition:** `> 500ms` for 2 minutes
- **Normal baseline:** 20-50ms
- **During failure:** 1000ms+ (CPU-bound)

**Priority:** P2 (High)

---

### 4. Recommendation Service Latency (High)

**Triggers on:** `recommendationCacheFailure` feature flag

**Type:** Tracing - Threshold

**Coralogix Setup:**
- **Alert Type:** Tracing - Threshold
- **Service:** `recommendation`
- **Operation:** `ListRecommendations`
- **Metric:** P95 latency
- **Condition:** `> 300ms` for 2 minutes
- **Normal baseline:** 30-80ms
- **During failure:** 500ms-2s (cache bypass)

**Priority:** P2 (High)

---

### 5. Recommendation Cache Miss Rate (Medium)

**Triggers on:** `recommendationCacheFailure` feature flag

**Type:** Logs - Threshold

**Coralogix Setup:**
- **Alert Type:** Logs - Threshold
- **Query:** `service.name:"recommendation" AND "cache miss"`
- **Condition:** `> 10 occurrences` in 5 minutes
- **Normal baseline:** 0 (cache disabled = no cache miss logs)
- **During failure:** Constant stream of cache miss logs

**Alternative (Tracing attribute):**
- **Alert Type:** Tracing - Threshold
- **Filter:** `service.name = "recommendation" AND app.cache_hit = false`
- **Condition:** `> 50%` of spans have cache_hit=false

**Priority:** P3 (Medium)

---

### 6. Product Catalog Error Rate (Critical)

**Triggers on:** `productCatalogFailure` feature flag

**Type:** Tracing - Threshold

**Coralogix Setup:**
- **Alert Type:** Tracing - Threshold
- **Service:** `product-catalog`
- **Metric:** Error rate
- **Condition:** `> 5%` for 2 minutes
- **Normal baseline:** 0%
- **During failure:** High error rate on specific product lookups

**Alternative (Logs):**
- **Alert Type:** Logs - Threshold
- **Query:** `service.name:"product-catalog" AND level:"error"`
- **Condition:** `> 5 occurrences` in 2 minutes

**Priority:** P1 (Critical)

---

### 7. Checkout Service Failures (Critical)

**Triggers on:** Any upstream failure (payment, catalog, cart)

**Type:** Tracing - Threshold

**Coralogix Setup:**
- **Alert Type:** Tracing - Threshold
- **Service:** `checkout`
- **Operation:** `PlaceOrder`
- **Metric:** Error rate
- **Condition:** `> 10%` for 2 minutes
- **Normal baseline:** 0-2%
- **During failure:** Cascades from payment/catalog failures

**Priority:** P1 (Critical)

---

### 8. Kafka Consumer Lag (High)

**Triggers on:** `kafkaQueueProblems` feature flag

**Type:** Metric - Threshold

**Coralogix Setup:**
- **Alert Type:** Metric - Threshold
- **Metric:** `kafka_consumer_group_lag` or `messaging.kafka.consumer.lag`
- **Condition:** `> 1000 messages` for 3 minutes
- **Normal baseline:** 0-50 messages
- **During failure:** Rapidly increasing lag

**Alternative (Logs):**
- **Alert Type:** Logs - Threshold
- **Query:** `service.name:"accounting" OR service.name:"fraud-detection" AND "lag" OR "delay"`
- **Condition:** Pattern detection

**Priority:** P2 (High)

---

### 9. Email Service Memory Pressure (High)

**Triggers on:** `emailMemoryLeak` feature flag

**Type:** Metric - Threshold

**Coralogix Setup:**
- **Alert Type:** Metric - Threshold
- **Metric:** `container.memory.usage` or `process.runtime.ruby.memory`
- **Filter:** `service.name = "email"`
- **Condition:** `> 80%` of limit for 2 minutes
- **Normal baseline:** 20-40%
- **During failure:** Grows toward 100%, then OOM

**Alternative (Logs - OOM detection):**
- **Alert Type:** Logs - Immediate
- **Query:** `k8s.container.name:"email" AND ("OOM" OR "killed" OR "out of memory")`
- **Condition:** Any occurrence

**Priority:** P2 (High)

---

### 10. Image Provider Latency (Medium)

**Triggers on:** `imageSlowLoad` feature flag

**Type:** Tracing - Threshold

**Coralogix Setup:**
- **Alert Type:** Tracing - Threshold
- **Service:** `image-provider`
- **Metric:** P95 latency
- **Condition:** `> 3000ms` for 2 minutes
- **Normal baseline:** 50-200ms
- **During failure:** 5000-10000ms (per flag setting)

**Priority:** P3 (Medium)

---

### 11. Frontend Error Rate (High)

**Triggers on:** Any upstream failure (cascading)

**Type:** Tracing - Threshold

**Coralogix Setup:**
- **Alert Type:** Tracing - Threshold
- **Service:** `frontend`
- **Metric:** Error rate
- **Condition:** `> 5%` for 3 minutes
- **Normal baseline:** 0-1%
- **During failure:** Reflects upstream issues

**Priority:** P2 (High)

---

### 12. Traffic Spike Detection (Medium)

**Triggers on:** `loadGeneratorFloodHomepage` feature flag

**Type:** Metric - Anomaly

**Coralogix Setup:**
- **Alert Type:** Metric - Anomaly (recommended) or Threshold
- **Metric:** Request rate (RPS)
- **Filter:** `service.name = "frontend" OR service.name = "frontend-proxy"`
- **Condition (threshold):** `> 500 req/s` (adjust to your baseline × 3)
- **Condition (anomaly):** Significant deviation from learned baseline
- **Normal baseline:** ~50-100 req/s (load generator normal mode)
- **During failure:** 500+ req/s flood

**Priority:** P3 (Medium)

---

### 13. Pod Crash / Restart Detection (Critical)

**Triggers on:** Any severe failure causing container crashes

**Type:** Metric - Threshold

**Coralogix Setup:**
- **Alert Type:** Metric - Threshold
- **Metric:** `kube_pod_container_status_restarts_total`
- **Filter:** `namespace = "otel-demo"`
- **Condition:** `> 2 restarts` in 10 minutes per pod
- **Normal baseline:** 0 restarts

**Priority:** P1 (Critical)

---

## Creating Alerts in Coralogix UI

### For Metric Alerts:

1. Navigate to **Alerts** → **New Alert**
2. Select **Metric** type
3. Choose **Metric - Threshold** or **Metric - Anomaly**
4. Enter the PromQL-style query
5. Set condition and duration
6. Configure notification channel (incident.io webhook)

### For Tracing Alerts:

1. Navigate to **Alerts** → **New Alert**
2. Select **Tracing** type
3. Choose **Tracing - Threshold** or **Tracing - Immediate**
4. Filter by service name and operation
5. Set latency or error rate threshold
6. Configure notification channel

### For Logs Alerts:

1. Navigate to **Alerts** → **New Alert**
2. Select **Standard** type
3. Choose **Logs - Threshold** or **Logs - Immediate**
4. Enter Lucene query
5. Set occurrence threshold
6. Configure notification channel

---

## incident.io Integration

### Webhook Configuration

In Coralogix, configure your incident.io webhook as the notification destination:

1. Go to **Settings** → **Integrations** → **Outgoing Webhooks** (or use the native incident.io integration if available)
2. Add your incident.io ingest webhook URL
3. Map alert priority to incident.io severity:
   - P1 → Critical
   - P2 → High  
   - P3 → Medium

### Alert Payload (if using generic webhook)

Coralogix sends structured JSON; incident.io can parse:
- `alert.name` → Incident title
- `alert.priority` → Severity
- `alert.description` → Summary
- `alert.labels` → Custom fields (service, scenario)

---

## Testing Your Alerts

### Step 1: Verify baseline (no alerts)

```bash
# Check current status - should show no active incidents
./incidentfox/scripts/trigger-incident.sh --status

# Wait 5-10 minutes, verify no alerts fire in Coralogix
```

### Step 2: Trigger a failure

```bash
# Start with payment failure (most dramatic)
./incidentfox/scripts/trigger-incident.sh service-failure

# Expected: "Payment Error Rate" alert fires within 2-3 minutes
```

### Step 3: Verify incident.io receives the alert

Check incident.io dashboard for new incident created.

### Step 4: Clear the failure

```bash
./incidentfox/scripts/trigger-incident.sh clear-all

# Expected: Alert resolves within 3-5 minutes
```

### Step 5: Test all scenarios

```bash
# High CPU
./incidentfox/scripts/trigger-incident.sh high-cpu
# Wait for alert, then clear

# Cache failure  
./incidentfox/scripts/trigger-incident.sh cache-failure
# Wait for alert, then clear

# ... repeat for each scenario
```

---

## Recommended Alert Priority

| Priority | Alerts | Auto-create incident? |
|----------|--------|----------------------|
| **P1 (Critical)** | Payment Error, Catalog Error, Checkout Failure, Pod Crashes | Yes, immediately |
| **P2 (High)** | High CPU, Latency Spikes, Kafka Lag, Memory Pressure, Frontend Errors | Yes, after 2 min |
| **P3 (Medium)** | Cache Miss, Image Slow, Traffic Spike | Yes, after 5 min |

---

## Tuning Thresholds

If alerts fire during normal operation, **increase thresholds**:
- Latency: increase by 50%
- Error rate: increase by 2-3%
- CPU/Memory: increase by 10%

If alerts don't fire during failure injection, **decrease thresholds**:
- Check that telemetry is flowing to Coralogix (verify in Explore)
- Ensure feature flags are actually toggling (check flagd logs)
- Reduce threshold or detection window

---

## Next Steps

1. Create these alerts in Coralogix using the Alert Management UI
2. Configure incident.io as notification destination
3. Test each scenario end-to-end
4. Tune thresholds based on your specific environment

