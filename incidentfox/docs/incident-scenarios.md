# Incident Scenarios

This document catalogs all available incident scenarios in the OpenTelemetry Demo, including how to trigger them and what to expect.

## Overview

The demo uses **feature flags** (via flagd) to enable various failure modes. This allows reproducible incident testing without code changes.

All scenarios can be triggered via:
1. The `trigger-incident.sh` script (recommended)
2. The flagd UI at http://localhost:8080/feature
3. Direct editing of `src/flagd/demo.flagd.json`

## Scenario Catalog

### 1. High CPU Load

**Scenario ID:** `high-cpu`

**Flag:** `adHighCpu`

**Affected Service:** `ad` (Advertisement Service)

**Description:** Triggers excessive CPU usage in the Ad service, simulating a compute-intensive operation or infinite loop.

**Symptoms:**
- CPU usage spikes to 80-100% for ad service
- Increased response latency from ad service
- Potential timeouts in frontend when calling ad service

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh high-cpu

# Or manually
./incidentfox/scripts/scenarios/high-cpu.sh
```

**Expected Metrics:**
```promql
# CPU usage spike
rate(process_cpu_seconds_total{service_name="ad"}[1m]) > 0.8

# Increased latency
histogram_quantile(0.99, 
  rate(http_server_duration_bucket{service_name="ad"}[5m])) > 1.0
```

**Resolution:**
- Turn off the feature flag
- Scale the ad service horizontally (k8s)
- The service recovers immediately when flag is disabled

---

### 2. Memory Leak

**Scenario ID:** `memory-leak`

**Flag:** `emailMemoryLeak`

**Affected Service:** `email`

**Description:** Gradually allocates memory without releasing it, simulating a memory leak.

**Variants:**
- `1x` - Slow leak (10MB/min)
- `10x` - Medium leak (100MB/min)
- `100x` - Fast leak (1GB/min)
- `1000x` - Very fast leak (10GB/min)

**Symptoms:**
- Steadily increasing memory usage
- Eventual OOM (Out of Memory) kill
- Service restarts
- Degraded performance before OOM

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh memory-leak

# Specify severity
./incidentfox/scripts/scenarios/memory-leak.sh 100x
```

**Expected Metrics:**
```promql
# Memory growth
increase(process_resident_memory_bytes{service_name="email"}[5m]) > 100000000

# Container restarts
increase(kube_pod_container_status_restarts_total{pod=~"email.*"}[10m]) > 0
```

**Resolution:**
- Turn off feature flag
- Service needs restart to clear leaked memory
- In Kubernetes, let it crash and restart automatically

---

### 3. Service Failure

**Scenario ID:** `service-failure`

**Flag:** `paymentFailure`

**Affected Service:** `payment`

**Description:** Payment service returns errors for a percentage of requests.

**Variants:**
- `10%` - 10% of charges fail
- `25%` - 25% of charges fail
- `50%` - 50% of charges fail
- `75%` - 75% of charges fail
- `90%` - 90% of charges fail
- `100%` - All charges fail

**Symptoms:**
- Increased HTTP 500 errors from payment service
- Failed checkout attempts
- Error logs in payment service
- User complaints about payment failures

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh service-failure

# Specify failure rate
./incidentfox/scripts/scenarios/service-failure.sh 50%
```

**Expected Metrics:**
```promql
# Error rate
sum(rate(http_server_requests_total{
  service_name="payment",
  http_status_code=~"5.."
}[5m])) / sum(rate(http_server_requests_total{
  service_name="payment"
}[5m])) > 0.1
```

**Expected Traces:**
- Traces with error tags in Jaeger
- Failed checkout spans

**Resolution:**
- Turn off feature flag
- Service is healthy, just simulating failures

---

### 4. Service Unreachable

**Scenario ID:** `service-unreachable`

**Flag:** `paymentUnreachable`

**Affected Service:** `payment`

**Description:** Payment service becomes completely unavailable (returns no response).

**Symptoms:**
- Connection timeouts to payment service
- Checkout completely broken
- Circuit breakers may trigger in checkout service

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh service-unreachable
```

**Expected Metrics:**
```promql
# Service down
up{service_name="payment"} == 0

# Increased timeout errors
increase(http_client_request_duration_seconds_count{
  service_name="checkout",
  error="timeout"
}[5m]) > 10
```

**Resolution:**
- Turn off feature flag
- Service recovers immediately

---

### 5. Latency Spike

**Scenario ID:** `latency-spike`

**Flag:** `imageSlowLoad`

**Affected Service:** `image-provider`

**Description:** Image loading becomes very slow, affecting page load times.

**Variants:**
- `5sec` - 5 second delay
- `10sec` - 10 second delay

**Symptoms:**
- Slow page loads
- Increased p95/p99 latencies
- Browser timeouts
- Poor user experience

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh latency-spike

# Specify delay
./incidentfox/scripts/scenarios/latency-spike.sh 10sec
```

**Expected Metrics:**
```promql
# High latency
histogram_quantile(0.99, 
  rate(http_server_duration_bucket{service_name="image-provider"}[5m])
) > 5.0
```

**Resolution:**
- Turn off feature flag
- Latency returns to normal immediately

---

### 6. Kafka Queue Problems

**Scenario ID:** `kafka-lag`

**Flag:** `kafkaQueueProblems`

**Affected Services:** `checkout`, `accounting`, `fraud-detection`

**Description:** Kafka queue gets overloaded while consumers slow down, causing message lag.

**Symptoms:**
- Growing Kafka consumer lag
- Delayed order processing
- Backpressure in checkout service
- accounting/fraud-detection fall behind

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh kafka-lag
```

**Expected Metrics:**
```promql
# Kafka lag
kafka_consumer_lag{topic="orders"} > 1000

# Message backlog
kafka_server_log_logendoffset - kafka_consumer_currentoffset > 100
```

**Resolution:**
- Turn off feature flag
- Consumers will catch up gradually
- May take 5-10 minutes to clear backlog

---

### 7. Cache Failure

**Scenario ID:** `cache-failure`

**Flag:** `recommendationCacheFailure`

**Affected Service:** `recommendation`

**Description:** Recommendation service cache starts failing, forcing more expensive operations.

**Symptoms:**
- Increased latency in recommendation service
- Higher CPU usage
- More calls to product-catalog service
- Degraded product page performance

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh cache-failure
```

**Expected Metrics:**
```promql
# Increased latency
histogram_quantile(0.95, 
  rate(http_server_duration_bucket{service_name="recommendation"}[5m])
) > 0.5

# Cache miss rate
rate(recommendation_cache_misses_total[5m]) > 10
```

**Resolution:**
- Turn off feature flag
- Cache recovers immediately

---

### 8. Catalog Failure

**Scenario ID:** `catalog-failure`

**Flag:** `productCatalogFailure`

**Affected Service:** `product-catalog`

**Description:** Product catalog service fails for specific products.

**Symptoms:**
- Product pages return errors
- Search results incomplete
- Recommendations may fail
- Cart operations may fail

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh catalog-failure
```

**Expected Traces:**
- Error spans in product-catalog
- Failed requests from frontend, recommendation, cart

**Resolution:**
- Turn off feature flag

---

### 9. Ad Service Garbage Collection

**Scenario ID:** `ad-gc-pressure`

**Flag:** `adManualGc`

**Affected Service:** `ad` (Java)

**Description:** Forces frequent full GC pauses in the Java-based ad service.

**Symptoms:**
- Intermittent latency spikes (GC pauses)
- Request queueing
- Timeout errors
- Sawtooth memory pattern

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh ad-gc-pressure
```

**Expected Metrics:**
```promql
# GC time
rate(jvm_gc_pause_seconds_sum{service_name="ad"}[5m]) > 0.1

# GC frequency
rate(jvm_gc_pause_seconds_count{service_name="ad"}[1m]) > 1
```

**Resolution:**
- Turn off feature flag
- GC returns to normal

---

### 10. Homepage Flood

**Scenario ID:** `traffic-spike`

**Flag:** `loadGeneratorFloodHomepage`

**Affected Service:** All (via `load-generator`)

**Description:** Load generator floods the homepage with excessive requests.

**Symptoms:**
- Massive traffic spike
- Increased latency across all services
- Potential rate limiting
- Resource exhaustion

**Trigger:**
```bash
./incidentfox/scripts/trigger-incident.sh traffic-spike
```

**Expected Metrics:**
```promql
# Request rate spike
sum(rate(http_server_requests_total[1m])) > 100

# Resource usage increases across all services
```

**Resolution:**
- Turn off feature flag
- Traffic returns to normal load levels

---

### 11. LLM Inaccurate Response

**Scenario ID:** `llm-inaccuracy`

**Flag:** `llmInaccurateResponse`

**Affected Service:** `product-reviews`

**Description:** LLM returns incorrect product summary for a specific product.

**Symptoms:**
- Data quality issue (incorrect AI-generated content)
- No performance impact
- May affect user trust

**Trigger:**
```bash
./incidentfox/scripts/scenarios/llm-inaccuracy.sh
```

**Resolution:**
- Turn off feature flag
- LLM returns accurate summaries

---

### 12. LLM Rate Limit

**Scenario ID:** `llm-rate-limit`

**Flag:** `llmRateLimitError`

**Affected Service:** `product-reviews`

**Description:** LLM service intermittently returns rate limit errors.

**Symptoms:**
- Some product reviews fail to load
- Error logs in product-reviews service
- Fallback to cached summaries

**Trigger:**
```bash
./incidentfox/scripts/scenarios/llm-rate-limit.sh
```

**Expected Logs:**
- "Rate limit exceeded" errors in product-reviews service

**Resolution:**
- Turn off feature flag

---

## Multi-Service Scenarios

### Cascading Failure

Trigger multiple related failures:

```bash
# Payment fails → Checkout errors → Cart abandoned
./incidentfox/scripts/trigger-incident.sh service-failure
./incidentfox/scripts/trigger-incident.sh kafka-lag
```

### Resource Exhaustion

```bash
# Multiple services consuming resources
./incidentfox/scripts/trigger-incident.sh high-cpu
./incidentfox/scripts/trigger-incident.sh memory-leak
./incidentfox/scripts/trigger-incident.sh traffic-spike
```

## Creating Custom Scenarios

To add a new scenario:

1. **Add feature flag** to `src/flagd/demo.flagd.json`
2. **Implement behavior** in the affected service
3. **Create trigger script** in `incidentfox/scripts/scenarios/`
4. **Document here** with symptoms and resolution

Example flag:
```json
{
  "myNewFailure": {
    "description": "Description of the failure",
    "state": "ENABLED",
    "variants": {
      "on": true,
      "off": false
    },
    "defaultVariant": "off"
  }
}
```

## Monitoring Incidents

### Grafana Dashboards

View pre-built dashboards at http://localhost:8080/grafana:

- **Demo Dashboard** - Overall system health
- **Span Metrics** - Trace-based metrics
- **Service Dashboard** - Per-service details

### Real-time Logs

```bash
# Docker Compose
docker compose logs -f <service-name>

# Kubernetes
kubectl logs -f -n otel-demo -l app=<service-name>
```

### Query Traces

```bash
# Find error traces
curl 'http://localhost:16686/api/traces?service=payment&tags={"error":"true"}'
```

## Agent Testing Checklist

For each scenario, verify your agent can:

- [ ] **Detect** - Identify the incident from metrics/logs/traces
- [ ] **Localize** - Determine which service(s) are affected
- [ ] **Diagnose** - Identify root cause from telemetry data
- [ ] **Remediate** - Take action (disable flag, scale, restart)
- [ ] **Verify** - Confirm the issue is resolved

## Scenario Cheat Sheet

| Scenario | Command | Duration | Auto-Recover |
|----------|---------|----------|--------------|
| High CPU | `trigger-incident.sh high-cpu` | Until disabled | No |
| Memory Leak | `trigger-incident.sh memory-leak` | Until OOM | Yes (restart) |
| Service Failure | `trigger-incident.sh service-failure` | Until disabled | No |
| Latency Spike | `trigger-incident.sh latency-spike` | Until disabled | No |
| Kafka Lag | `trigger-incident.sh kafka-lag` | Until disabled | Gradual |
| Cache Failure | `trigger-incident.sh cache-failure` | Until disabled | No |
| Traffic Spike | `trigger-incident.sh traffic-spike` | Until disabled | No |

## Further Reading

- Feature flag implementation: `src/flagd/demo.flagd.json`
- Service implementations: `src/<service>/`
- Load generator: `src/load-generator/locustfile.py`

