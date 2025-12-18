# Cascade Impact Analysis

This document provides detailed analysis of how each failure scenario impacts downstream services, helping understand how failures propagate through microservice architectures.

## Table of Contents

- [1. Cache Failure](#1-cache-failure)
- [2. Service Failure - Payment](#2-service-failure---payment)
- [3. High CPU - Ad Service](#3-high-cpu---ad-service)
- [4. Memory Leak - Email Service](#4-memory-leak---email-service)
- [5. Latency Spike - Image Provider](#5-latency-spike---image-provider)
- [6. Kafka Queue Problems](#6-kafka-queue-problems)
- [7. Catalog Failure](#7-catalog-failure)
- [8. Service Unreachable - Payment](#8-service-unreachable---payment)
- [9. Ad GC Pressure](#9-ad-gc-pressure)
- [10. Traffic Spike](#10-traffic-spike)
- [11. LLM Rate Limit](#11-llm-rate-limit)
- [12. LLM Inaccuracy](#12-llm-inaccuracy)

---

## 1. Cache Failure

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh cache-failure
```

### Failure Source
**Service:** `recommendation` (Recommendation Service)
**Component:** Internal cache

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
recommendation service cache ❌ FAILS
    │
    ├─ Cache misses: 100%
    ├─ Memory allocated for cache: wasted
    └─ Must compute recommendations on every request
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+30s)                           │
└─────────────────────────────────────────────────────────────┘
    
🔴 recommendation service
    ├─ Latency: 50ms → 500ms+ (10x increase)
    ├─ CPU usage: 20% → 60% (3x increase)
    ├─ Memory usage increases (no caching)
    └─ Thread pool pressure
    
    ↓
    
🟡 product-catalog service (DOWNSTREAM #1)
    ├─ Request rate: 10 req/s → 100 req/s (10x increase)
    │  └─ Why: recommendation must query for every request
    ├─ CPU usage: 15% → 45%
    ├─ Latency: 20ms → 80ms
    └─ Database connection pool pressure
    
    ↓
    
🟠 frontend service (DOWNSTREAM #2)
    ├─ Product page load time: 200ms → 800ms
    ├─ Recommendation widget: slow or timeout
    ├─ User-visible impact: "Loading..." delays
    └─ Potential timeout errors (if > 3s)
    
    ↓
    
🟠 load-generator (DOWNSTREAM #3)
    ├─ Request success rate may drop
    ├─ Increased error rate in automated tests
    └─ SLO violations detected

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+5min)                        │
└─────────────────────────────────────────────────────────────┘

🔴 Database (PostgreSQL) - backing product-catalog
    ├─ Query load increases 10x
    ├─ Connection pool exhaustion risk
    └─ Disk I/O increases

🟡 OTEL Collector
    ├─ Trace volume increases (more spans)
    ├─ Metric cardinality increases
    └─ Memory usage increases

🟡 Observability Stack
    ├─ Jaeger: More error traces
    ├─ Prometheus: Alert firing
    └─ Grafana: Dashboard shows degradation
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `recommendation` | 🔴 Critical | Latency 10x, CPU 3x | Immediate (flag off) |
| `product-catalog` | 🟡 Moderate | Load 10x, CPU 3x | 30s after fix |
| `frontend` | 🟠 Minor | Page load 4x slower | Immediate (flag off) |
| `postgresql` | 🟡 Moderate | Query load 10x | 1-2 min after fix |
| `load-generator` | 🟠 Minor | Test failures | Immediate |

### Detection Metrics

```promql
# Primary signal
histogram_quantile(0.95, 
  rate(http_server_duration_bucket{service_name="recommendation"}[5m])
) > 0.5

# Cache miss rate
rate(recommendation_cache_misses_total[5m]) > 10

# Downstream impact
rate(http_server_requests_total{
  service_name="product-catalog",
  caller="recommendation"
}[5m]) > 50
```

### Diagnosis Difficulty
🟢 **Easy** - Clear cache metrics, obvious latency spike, clean dependency chain

---

## 2. Service Failure - Payment

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh service-failure 50%
```

### Failure Source
**Service:** `payment`
**Failure Mode:** Returns HTTP 500 for 50% of requests

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
payment service ❌ 50% FAILURE RATE
    │
    ├─ HTTP 500 for 50% of charge requests
    ├─ Service is healthy (not crashed)
    └─ Intermittent failures (hard to debug)
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+10s)                           │
└─────────────────────────────────────────────────────────────┘
    
🔴 checkout service (DOWNSTREAM #1)
    ├─ 50% of checkout operations fail
    ├─ Error handling logic triggered
    ├─ Failed transactions logged
    ├─ Retry logic may activate (making it worse)
    └─ Publishes failure events to Kafka
    
    ↓ (splits into two paths)
    
Path A: Frontend User Impact
─────────────────────────────
🟠 frontend service (DOWNSTREAM #2)
    ├─ "Payment failed" errors shown to users
    ├─ User experience degraded
    ├─ Potential retry attempts by users
    ├─ Shopping cart abandonment increases
    └─ Revenue loss

Path B: Backend Processing Impact  
─────────────────────────────────
🟡 kafka message queue (DOWNSTREAM #3)
    ├─ Receives mixed success/failure events
    ├─ Message volume increases (failures + retries)
    └─ Consumer load increases
    
    ↓
    
🟡 accounting service (DOWNSTREAM #4)
    ├─ Processes failure events
    ├─ Must handle both success and failed orders
    ├─ Reconciliation becomes complex
    ├─ Alert on high failure rate
    └─ Manual investigation needed
    
🟡 fraud-detection service (DOWNSTREAM #5)
    ├─ Analyzes failed payment patterns
    ├─ May flag legitimate failures as fraud
    ├─ False positive rate increases
    └─ Alert noise

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+30min)                       │
└─────────────────────────────────────────────────────────────┘

🟠 cart service
    ├─ Items remain in cart (not cleared)
    ├─ Abandoned cart rate increases
    └─ Storage pressure over time

🟠 Business Metrics
    ├─ Conversion rate: drops 50%
    ├─ Revenue: drops 50%
    ├─ Customer support tickets: increase
    └─ Brand reputation impact

🟡 Monitoring/Alerting
    ├─ PagerDuty/alert system triggered
    ├─ On-call engineer paged
    ├─ Incident investigation started
    └─ War room potentially needed
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `payment` | 🔴 Critical | 50% error rate | Immediate (flag off) |
| `checkout` | 🔴 Critical | 50% failed operations | Immediate |
| `frontend` | 🟠 Moderate | User errors, UX degraded | Immediate |
| `kafka` | 🟡 Minor | Increased message volume | 5-10 min backlog |
| `accounting` | 🟡 Minor | Complex reconciliation | Manual cleanup |
| `fraud-detection` | 🟡 Minor | False positives | Immediate |
| `cart` | 🟠 Minor | Abandoned carts | Gradual cleanup |

### Detection Metrics

```promql
# Primary signal - error rate
sum(rate(http_server_requests_total{
  service_name="payment",
  http_status_code=~"5.."
}[5m])) / sum(rate(http_server_requests_total{
  service_name="payment"
}[5m])) > 0.1

# Downstream impact - checkout failures
sum(rate(http_server_requests_total{
  service_name="checkout",
  http_status_code=~"5.."
}[5m]))

# Business impact
rate(checkout_failed_total[5m]) > 10
```

### Diagnosis Difficulty
🟢 **Easy** - Clear error metrics, obvious logs, traceable in Jaeger

### Business Impact
💰 **High** - Direct revenue loss, customer dissatisfaction

---

## 3. High CPU - Ad Service

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh high-cpu
```

### Failure Source
**Service:** `ad`
**Failure Mode:** CPU usage 80-100%

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
ad service ❌ HIGH CPU (80-100%)
    │
    ├─ Compute-intensive operation or infinite loop
    ├─ Thread pool exhaustion
    ├─ Request queue builds up
    └─ Response times increase dramatically
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+30s)                           │
└─────────────────────────────────────────────────────────────┘
    
🔴 ad service
    ├─ Response time: 50ms → 3000ms+ (60x)
    ├─ CPU: 80-100% (saturated)
    ├─ Request queue length: 0 → 100+
    ├─ Thread pool: exhausted
    └─ May trigger circuit breakers in clients
    
    ↓
    
🟠 frontend service (DOWNSTREAM #1)
    ├─ Ad widget loading: slow or timeout
    ├─ Page render blocked (if synchronous)
    ├─ Timeout errors after 3-5 seconds
    ├─ Fallback to "no ads" mode (if implemented)
    └─ Page load time: +3-5 seconds
    
    User Experience:
    ├─ Homepage loads slowly
    ├─ Product pages missing ads
    └─ Blank spaces where ads should be

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+30s to T+5min)                         │
└─────────────────────────────────────────────────────────────┘

🟡 load-generator (DOWNSTREAM #2)
    ├─ Automated user flows timing out
    ├─ Test failure rate increases
    └─ Load test metrics skewed

🟠 Kubernetes/Container Platform
    ├─ CPU throttling may trigger
    ├─ OOMKiller may activate (if memory also affected)
    ├─ Pod restart possible
    └─ Health check may fail

🟡 Node-level Impact (if on shared node)
    ├─ Other pods on same node affected
    ├─ Node CPU: increases
    ├─ Noisy neighbor problem
    └─ Potential node pressure

🟡 Business Impact
    ├─ Ad revenue: $0 (ads not displayed)
    ├─ User experience: degraded
    └─ SEO impact: slower page loads
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `ad` | 🔴 Critical | CPU 100%, Latency 60x | Immediate (flag off) |
| `frontend` | 🟠 Moderate | Page load +5s, timeouts | Immediate |
| `load-generator` | 🟡 Minor | Test failures | Immediate |
| Other pods on same node | 🟡 Minor | Noisy neighbor | Immediate |

### Detection Metrics

```promql
# Primary signal - CPU saturation
rate(process_cpu_seconds_total{service_name="ad"}[1m]) > 0.8

# Latency impact
histogram_quantile(0.99, 
  rate(http_server_duration_bucket{service_name="ad"}[5m])
) > 1.0

# Request queue
http_server_requests_active{service_name="ad"} > 50
```

### Diagnosis Difficulty
🟢 **Very Easy** - CPU metric is obvious, clear single service issue

### Business Impact
💰 **Low-Medium** - Lost ad revenue, degraded UX, non-critical

---

## 4. Memory Leak - Email Service

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh memory-leak
```

### Failure Source
**Service:** `email`
**Failure Mode:** Memory leak (gradual memory growth)

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE (GRADUAL)                                   │
└─────────────────────────────────────────────────────────────┘
email service ❌ MEMORY LEAK
    │
    ├─ Memory: 100MB → 500MB → 1GB → OOM
    ├─ Leak rate: depends on variant (1x/10x/100x/1000x)
    ├─ Time to OOM: 10min (1000x) to 10h (1x)
    └─ Progressive degradation before crash
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: GRADUAL DEGRADATION (T+0 to T+5min)               │
└─────────────────────────────────────────────────────────────┘
    
🟡 email service
    ├─ Memory usage: steadily increasing
    ├─ GC frequency: increases
    ├─ GC pause time: increases
    ├─ Latency: slightly increases (50ms → 200ms)
    └─ CPU usage: increases (GC overhead)
    
    ↓
    
🟢 checkout service (DOWNSTREAM #1)
    ├─ Email sends: working but slower
    ├─ Occasional timeout warnings
    └─ No user-visible impact yet

┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: SEVERE DEGRADATION (T+5min to T+9min)             │
└─────────────────────────────────────────────────────────────┘

🟠 email service
    ├─ Memory: approaching limit (800MB/1GB)
    ├─ GC: constant (stop-the-world pauses)
    ├─ Latency: 200ms → 5000ms
    ├─ CPU: 80%+ (mostly GC)
    └─ Request queue building up
    
    ↓
    
🟡 checkout service (DOWNSTREAM #1)
    ├─ Email send timeouts: frequent
    ├─ Retry logic triggered
    ├─ Checkout still succeeds but emails delayed
    └─ Error logs increase
    
    ↓
    
🟠 frontend/users (DOWNSTREAM #2)
    ├─ Order confirmation: "Email will arrive shortly"
    ├─ Users don't receive immediate confirmation
    └─ Support tickets may increase

┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: CRASH (T+10min)                                    │
└─────────────────────────────────────────────────────────────┘

🔴 email service
    ├─ OOMKilled by Kubernetes
    ├─ Pod restart initiated
    ├─ All in-flight requests lost
    └─ Service unavailable for 10-30s
    
    ↓
    
🟡 checkout service (DOWNSTREAM #1)
    ├─ Email service unreachable
    ├─ All email requests fail
    ├─ Checkouts still succeed (async email)
    └─ Queued emails may be lost
    
    ↓
    
🟠 Users
    ├─ No confirmation emails
    ├─ Confusion about order status
    └─ Support contact increase

┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: RESTART LOOP (if flag still on)                   │
└─────────────────────────────────────────────────────────────┘

🔴 email service
    ├─ Restarts with clean memory
    ├─ Leak continues (flag still on)
    ├─ Crashes again in 10min
    └─ CrashLoopBackOff pattern
    
    ↓
    
🟠 Kubernetes
    ├─ Exponential backoff on restarts
    ├─ Service degraded availability
    └─ Alert storm

🟡 checkout service
    ├─ Intermittent email service availability
    ├─ Circuit breaker may open
    └─ Email queue builds up
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `email` | 🔴 Critical | OOM kill, crash loop | Needs restart + flag off |
| `checkout` | 🟡 Minor | Timeout errors, no email | Immediate (flag off) |
| `users` | 🟠 Moderate | No confirmation emails | Manual follow-up |
| `kubernetes` | 🟡 Minor | Resource thrashing | After pod stable |

### Detection Metrics

```promql
# Primary signal - memory growth
increase(process_resident_memory_bytes{service_name="email"}[5m]) > 100000000

# Container restarts
increase(kube_pod_container_status_restarts_total{pod=~"email.*"}[10m]) > 0

# GC pressure
rate(jvm_gc_pause_seconds_sum{service_name="email"}[1m]) > 0.5
```

### Diagnosis Difficulty
🟡 **Medium** - Gradual failure, need to correlate memory growth with time

### Business Impact
💰 **Medium** - Lost emails, customer confusion, support load

---

## 5. Latency Spike - Image Provider

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh latency-spike
```

### Failure Source
**Service:** `image-provider`
**Failure Mode:** 5-10 second delay on image loads

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
image-provider service ❌ SLOW (5-10s delay)
    │
    ├─ Image requests: 50ms → 5000ms (100x slower)
    ├─ Service is healthy (just slow)
    └─ Network/disk I/O simulation
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+30s)                           │
└─────────────────────────────────────────────────────────────┘
    
🟠 frontend service (DOWNSTREAM #1)
    ├─ Page load waiting for images
    ├─ Layout shift (images load late)
    ├─ Time to First Contentful Paint (FCP): +5s
    ├─ Largest Contentful Paint (LCP): +5s
    └─ Core Web Vitals: degraded
    
    User Experience:
    ├─ Pages load in stages
    │   └─ Text/HTML → 200ms ✓
    │   └─ Images → 5000ms ❌
    ├─ Broken image placeholders initially
    ├─ Layout jumps when images finally load
    └─ Frustrating slow experience
    
    ↓
    
🟡 frontend-proxy (Envoy) (DOWNSTREAM #2)
    ├─ Connection pool held open longer
    ├─ Concurrent connection limit may be reached
    ├─ Request queue builds up
    └─ May start timing out (if timeout < 10s)
    
    ↓
    
🟡 Browser/End User
    ├─ Browser timeout possible (if no progress)
    ├─ User may refresh page (making it worse)
    ├─ Bounce rate increases
    └─ SEO ranking impact (Core Web Vitals)

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+10min)                       │
└─────────────────────────────────────────────────────────────┘

🟠 load-generator (DOWNSTREAM #3)
    ├─ Automated tests timing out
    ├─ Page load assertions failing
    └─ Test suite unreliable

🟡 CDN/Cache (if present)
    ├─ Cache miss rate may increase
    ├─ Slow origin pulls
    └─ CDN timeout to origin

🟡 Business Metrics
    ├─ Bounce rate: increases 30-50%
    ├─ Time on site: decreases
    ├─ Conversion rate: drops 10-20%
    └─ SEO ranking: gradually drops (hours/days)
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `image-provider` | 🔴 Critical | Latency 100x | Immediate (flag off) |
| `frontend` | 🟠 Moderate | Page load +5s, UX degraded | Immediate |
| `frontend-proxy` | 🟡 Minor | Connection pressure | Immediate |
| `load-generator` | 🟡 Minor | Test failures | Immediate |
| `end-users` | 🟠 Moderate | Poor UX, bounce | Immediate |

### Detection Metrics

```promql
# Primary signal - latency
histogram_quantile(0.99, 
  rate(http_server_duration_bucket{service_name="image-provider"}[5m])
) > 5.0

# Downstream impact - page load time
histogram_quantile(0.95,
  rate(http_server_duration_bucket{service_name="frontend"}[5m])
) > 3.0

# User experience - browser timing
browser_page_load_time_p95 > 5000
```

### Diagnosis Difficulty
🟢 **Easy** - Obvious latency spike, clear user impact

### Business Impact
💰 **Medium-High** - UX degradation, bounce rate, conversion loss, SEO impact

---

## 6. Kafka Queue Problems

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh kafka-lag
```

### Failure Source
**Service:** `kafka` + consumers (`accounting`, `fraud-detection`)
**Failure Mode:** Queue overload + slow consumers

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
kafka + consumers ❌ LAG BUILDING UP
    │
    ├─ Producer (checkout): publishing at normal rate
    ├─ Consumers: artificially slowed down
    ├─ Consumer lag: 0 → 100 → 1000+ messages
    └─ Message processing delay: seconds → minutes
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+2min)                          │
└─────────────────────────────────────────────────────────────┘
    
🟡 kafka broker
    ├─ Message queue depth: increasing
    ├─ Disk usage: increasing (retention period)
    ├─ Memory pressure: higher
    └─ Replication lag (if multi-broker)
    
    ↓ (splits into two consumer paths)
    
Path A: Accounting Service
─────────────────────────────
🟠 accounting service (CONSUMER #1)
    ├─ Consumer lag: 500+ messages
    ├─ Processing delay: 5-30 minutes
    ├─ Database writes: delayed
    ├─ Financial records: out of date
    └─ Reconciliation impossible until caught up
    
    Business Impact:
    ├─ Real-time revenue dashboard: stale
    ├─ Financial reports: inaccurate
    ├─ Refund processing: delayed
    └─ Audit trail: incomplete

Path B: Fraud Detection Service
─────────────────────────────────
🟠 fraud-detection service (CONSUMER #2)
    ├─ Consumer lag: 500+ messages
    ├─ Fraud analysis: delayed by minutes
    ├─ Real-time fraud detection: ineffective
    └─ Fraudulent orders: may go through
    
    Security Impact:
    ├─ Fraudulent transactions undetected
    ├─ Chargebacks increase
    ├─ Financial loss
    └─ Compliance issues

┌─────────────────────────────────────────────────────────────┐
│ UPSTREAM IMPACT (backpressure)                              │
└─────────────────────────────────────────────────────────────┘

🟡 checkout service (PRODUCER)
    ├─ Kafka publish: still succeeds (async)
    ├─ No immediate impact on checkout flow
    ├─ BUT: Kafka buffer may fill up
    └─ IF buffer full: checkout may block/fail
    
    ↓ (if backpressure severe)
    
🟠 checkout service (backpressure scenario)
    ├─ Kafka publish timeout
    ├─ Checkout fails for users
    ├─ Error messages displayed
    └─ Revenue loss

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+5min to T+30min)                       │
└─────────────────────────────────────────────────────────────┘

🟡 kafka broker
    ├─ Disk space: may fill up (if lag persists)
    ├─ Old messages retention: triggered
    ├─ Message loss: possible (if retention exceeded)
    └─ Cluster instability

🟡 postgresql (accounting database)
    ├─ Burst write load when consumers catch up
    ├─ Connection pool spike
    └─ Temporary performance degradation

🟠 Operations/Business
    ├─ Data freshness SLO violated
    ├─ Real-time analytics: unavailable
    ├─ Executive dashboard: "data delayed" warning
    └─ Manual reconciliation needed
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `kafka` | 🟡 Moderate | Queue depth, disk pressure | 5-10 min to drain |
| `accounting` | 🟠 Moderate | Processing delay, stale data | 10-30 min to catch up |
| `fraud-detection` | 🟠 Moderate | Detection delay, security risk | 10-30 min to catch up |
| `checkout` | 🟢 Minor | No immediate impact | - |
| `postgresql` | 🟡 Minor | Burst load on catch-up | After drain |

### Detection Metrics

```promql
# Primary signal - consumer lag
kafka_consumer_lag{topic="orders"} > 1000

# Message backlog
kafka_server_log_logendoffset - kafka_consumer_currentoffset > 100

# Processing delay
time() - kafka_consumer_last_commit_timestamp > 300
```

### Diagnosis Difficulty
🟡 **Medium** - Need to understand Kafka metrics, consumer behavior

### Business Impact
💰 **Medium-High** - Data freshness, fraud risk, financial accuracy, compliance

---

## 7. Catalog Failure

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh catalog-failure
```

### Failure Source
**Service:** `product-catalog`
**Failure Mode:** Fails to load specific products

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
product-catalog service ❌ PRODUCT LOAD FAILURES
    │
    ├─ Specific product IDs: return errors
    ├─ Database query fails (simulated)
    ├─ HTTP 500 or 404 for affected products
    └─ Other products: still working
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+30s)                           │
└─────────────────────────────────────────────────────────────┘
    
Path A: Frontend Display
─────────────────────────────
🔴 frontend service (DOWNSTREAM #1)
    ├─ Product detail pages: error or blank
    ├─ Product listings: incomplete (missing items)
    ├─ Search results: gaps
    └─ Error messages to users
    
    User Experience:
    ├─ "Product not found" errors
    ├─ Broken product pages
    ├─ Frustration and confusion
    └─ User may leave site

Path B: Recommendation Service
────────────────────────────────
🟠 recommendation service (DOWNSTREAM #2)
    ├─ Cannot fetch product details
    ├─ Recommendations fail for affected products
    ├─ Partial recommendation sets
    └─ Error handling triggered
    
    Impact:
    ├─ "You might also like" widget: broken
    ├─ Cross-sell opportunities: lost
    └─ Revenue impact

Path C: Cart Operations
────────────────────────────────
🟠 cart service (DOWNSTREAM #3)
    ├─ Cannot validate product in cart
    ├─ Product price lookup fails
    ├─ Cart display: incomplete
    └─ Add-to-cart: may fail
    
    Impact:
    ├─ Items in cart show as unavailable
    ├─ Checkout blocked
    └─ Cart abandonment

Path D: Checkout Flow
────────────────────────────────
🔴 checkout service (DOWNSTREAM #4)
    ├─ Product validation fails
    ├─ Cannot calculate order total
    ├─ Order submission blocked
    └─ Complete checkout failure
    
    Impact:
    ├─ Users cannot complete purchase
    ├─ Revenue loss: 100% for affected products
    └─ Critical business impact

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+10min)                       │
└─────────────────────────────────────────────────────────────┘

🟡 shipping service (DOWNSTREAM #5)
    ├─ Cannot calculate shipping (needs product weight/dimensions)
    ├─ Shipping quote fails
    └─ Checkout blocked at shipping step

🟠 Business Operations
    ├─ Support tickets spike
    ├─ Social media complaints
    ├─ Revenue loss for affected SKUs
    └─ Brand reputation damage

🟡 Search/Discovery
    ├─ Search index may be incomplete
    ├─ Category pages broken
    └─ SEO impact (broken links)
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `product-catalog` | 🔴 Critical | Product load failures | Immediate (flag off) |
| `frontend` | 🔴 Critical | Broken pages, errors | Immediate |
| `recommendation` | 🟠 Moderate | Failed recommendations | Immediate |
| `cart` | 🟠 Moderate | Cart validation fails | Immediate |
| `checkout` | 🔴 Critical | Cannot complete orders | Immediate |
| `shipping` | 🟡 Minor | Quote calculation fails | Immediate |

### Detection Metrics

```promql
# Primary signal - error rate
sum(rate(http_server_requests_total{
  service_name="product-catalog",
  http_status_code=~"5.."
}[5m])) / sum(rate(http_server_requests_total{
  service_name="product-catalog"
}[5m])) > 0.05

# Downstream impact - checkout failures
rate(checkout_failed_total{reason="product_unavailable"}[5m]) > 5
```

### Diagnosis Difficulty
🟢 **Easy** - Clear error logs, obvious user impact, error traces in Jaeger

### Business Impact
💰 **Critical** - Direct revenue loss, broken core functionality, customer dissatisfaction

---

## 8. Service Unreachable - Payment

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh service-unreachable
```

### Failure Source
**Service:** `payment`
**Failure Mode:** Service completely unavailable (no response)

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
payment service ❌ COMPLETELY DOWN
    │
    ├─ Service not responding
    ├─ Connection timeout (not refused)
    ├─ Health checks failing
    └─ No response after 30-60 seconds
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+30s)                           │
└─────────────────────────────────────────────────────────────┘
    
🔴 checkout service (DOWNSTREAM #1)
    ├─ Payment request: timeout after 30s
    ├─ Retry logic: attempts 3x (90s total)
    ├─ Circuit breaker: may OPEN after 5 failures
    ├─ All checkouts: FAIL
    └─ Kafka: publishes failure events
    
    Behavior cascade:
    ├─ First 5 requests: timeout (30s each)
    ├─ Circuit breaker opens
    ├─ Subsequent requests: fail immediately
    └─ "Service unavailable" to all users
    
    ↓
    
🔴 frontend service (DOWNSTREAM #2)
    ├─ Checkout button: "Payment unavailable"
    ├─ Error page displayed
    ├─ Users cannot complete ANY purchases
    └─ 100% checkout failure rate
    
    ↓
    
🔴 Business
    ├─ Revenue: $0 (complete halt)
    ├─ Conversion rate: 0%
    ├─ Cart abandonment: 100%
    └─ SEV-1 INCIDENT declared

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+30min)                       │
└─────────────────────────────────────────────────────────────┘

🟡 kafka (DOWNSTREAM #3)
    ├─ Only failure events (no successes)
    ├─ Message pattern change (detection signal)
    └─ Consumers receive only failures

🟡 accounting service (DOWNSTREAM #4)
    ├─ No successful transactions to process
    ├─ Only failed checkout events
    └─ Accounting team alerted

🟡 fraud-detection service (DOWNSTREAM #5)
    ├─ No transactions to analyze
    └─ Monitoring detects anomaly (zero transactions)

🟡 Monitoring/Alerting
    ├─ Service health check: CRITICAL
    ├─ Checkout success rate: 0%
    ├─ Revenue dashboard: flat line
    ├─ Multiple alerts fire
    ├─ PagerDuty: critical incident
    └─ War room initiated

🔴 Operations Response
    ├─ On-call engineer: paged immediately
    ├─ Incident commander: assigned
    ├─ Status page: updated
    ├─ Customer support: notified
    └─ Engineering team: mobilized

🟠 User Behavior
    ├─ Support tickets: flood
    ├─ Social media: complaints
    ├─ Users abandon site
    └─ Lost to competitors
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `payment` | 🔴 Critical | Service down, unreachable | Immediate (flag off) |
| `checkout` | 🔴 Critical | 100% failure, circuit open | 1-2 min (circuit reset) |
| `frontend` | 🔴 Critical | No checkouts possible | Immediate |
| `kafka` | 🟡 Minor | Only failure events | Immediate |
| `accounting` | 🟡 Minor | No txns to process | Immediate |
| `fraud-detection` | 🟡 Minor | No txns to analyze | Immediate |

### Detection Metrics

```promql
# Primary signal - service down
up{service_name="payment"} == 0

# Timeout errors
increase(http_client_request_duration_seconds_count{
  service_name="checkout",
  error="timeout",
  target="payment"
}[5m]) > 10

# Circuit breaker state
circuit_breaker_state{service="checkout",target="payment"} == 1  # OPEN

# Business impact
rate(checkout_success_total[5m]) == 0
```

### Diagnosis Difficulty
🟢 **Very Easy** - Obvious service down, health checks fail, clear timeout errors

### Business Impact
💰 **CRITICAL** - Complete revenue halt, SEV-1 incident, all-hands response

### Difference from Service Failure

| Aspect | Service Unreachable | Service Failure (50%) |
|--------|---------------------|----------------------|
| Service Health | Down | Up but returning errors |
| Error Type | Timeout | HTTP 500 |
| Impact | 100% failure | 50% failure |
| Detection | Immediate (health check) | Slower (need error rate) |
| Severity | SEV-1 | SEV-2 |
| Business Impact | Complete halt | Partial degradation |

---

## 9. Ad GC Pressure

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh ad-gc-pressure
```

### Failure Source
**Service:** `ad` (Java service)
**Failure Mode:** Frequent full GC pauses

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
ad service ❌ GC PRESSURE (Java)
    │
    ├─ Heap memory: repeatedly fills up
    ├─ Full GC triggered: every 5-10 seconds
    ├─ GC pause time: 100ms - 2000ms
    ├─ Service frozen during GC
    └─ Requests queued during pauses
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+30s)                           │
└─────────────────────────────────────────────────────────────┘
    
🟠 ad service
    ├─ Latency pattern: intermittent spikes
    │   └─ Normal: 50ms, 50ms, 50ms
    │   └─ GC pause: 1500ms
    │   └─ Normal: 50ms, 50ms
    │   └─ GC pause: 1500ms (sawtooth pattern)
    ├─ Request queueing during GC
    ├─ CPU: high (70-80% for GC)
    └─ Memory: sawtooth pattern (up → GC → down → up)
    
    ↓
    
🟡 frontend service (DOWNSTREAM #1)
    ├─ Ad widget: intermittent slow loads
    ├─ Some requests: 50ms (fast)
    ├─ Some requests: 1500ms (GC pause)
    ├─ Unpredictable performance
    └─ User experience: inconsistent
    
    User Experience:
    ├─ Most page loads: fine
    ├─ Some page loads: ads load late (visible pop-in)
    ├─ Frustrating unpredictability
    └─ Layout shift during ad load

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+10min)                       │
└─────────────────────────────────────────────────────────────┘

🟡 JVM/Container
    ├─ CPU time: 30% application, 70% GC
    ├─ Throughput: reduced 50%+
    ├─ Container CPU throttling: possible
    └─ Resource waste

🟡 Monitoring
    ├─ Latency alerts: flapping (on/off/on/off)
    ├─ Alert fatigue
    └─ Difficult to diagnose (intermittent)

🟠 load-generator (DOWNSTREAM #2)
    ├─ Test results: inconsistent
    ├─ P50 latency: normal
    ├─ P95/P99 latency: very high
    └─ Percentile alerts triggered
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `ad` | 🟠 Moderate | Intermittent GC pauses | Immediate (flag off) |
| `frontend` | 🟡 Minor | Inconsistent ad load | Immediate |
| `load-generator` | 🟡 Minor | P95/P99 degraded | Immediate |

### Detection Metrics

```promql
# Primary signal - GC time
rate(jvm_gc_pause_seconds_sum{service_name="ad"}[5m]) > 0.1

# GC frequency
rate(jvm_gc_pause_seconds_count{service_name="ad"}[1m]) > 1

# Latency impact (high percentiles)
histogram_quantile(0.99, 
  rate(http_server_duration_bucket{service_name="ad"}[5m])
) > 1.0

# Sawtooth memory pattern
rate(jvm_memory_used_bytes{service_name="ad",area="heap"}[1m])
```

### Diagnosis Difficulty
🟡 **Medium** - Need to understand JVM metrics, GC behavior, intermittent nature makes it tricky

### Business Impact
💰 **Low** - Minor UX inconsistency, non-critical service, no revenue loss

### Characteristics
- **Intermittent** - Not constant degradation
- **Predictable pattern** - Sawtooth memory, periodic pauses
- **Java-specific** - Requires JVM knowledge to diagnose
- **Percentile impact** - P50 fine, P99 bad

---

## 10. Traffic Spike

### Trigger Command
```bash
./incidentfox/scripts/trigger-incident.sh traffic-spike
```

### Failure Source
**Service:** `load-generator`
**Failure Mode:** Floods homepage with excessive traffic

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
load-generator ❌ TRAFFIC FLOOD
    │
    ├─ Normal load: 10 req/s
    ├─ Flood load: 500 req/s (50x increase)
    ├─ All traffic: homepage and checkout flows
    └─ Simulates: viral traffic, DDoS, bot attack
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+1min)                          │
└─────────────────────────────────────────────────────────────┘
    
🟡 frontend-proxy (Envoy) (FIRST HIT)
    ├─ Request rate: 10 req/s → 500 req/s
    ├─ Connection pool: filling up
    ├─ CPU usage: increases
    └─ May start rate limiting (if configured)
    
    ↓
    
🟠 frontend service (DOWNSTREAM #1)
    ├─ Request rate: 50x increase
    ├─ Thread pool: saturated
    ├─ CPU: 40% → 90%
    ├─ Memory: increases (request context)
    ├─ Latency: 100ms → 500ms
    └─ May start rejecting requests (503)
    
    ↓ (frontend calls multiple services)
    
🟠 Multiple Services SIMULTANEOUSLY:
    
    ad service (DOWNSTREAM #2)
    ├─ Request rate: 50x
    ├─ CPU: 30% → 80%
    ├─ Latency: 50ms → 300ms
    └─ Thread pool pressure
    
    cart service (DOWNSTREAM #3)
    ├─ Request rate: 50x
    ├─ Valkey connections: increase
    ├─ CPU: 25% → 70%
    └─ Cache hit ratio may drop
    
    product-catalog service (DOWNSTREAM #4)
    ├─ Request rate: 50x
    ├─ Database connections: spike
    ├─ CPU: 35% → 85%
    └─ Query queue building
    
    recommendation service (DOWNSTREAM #5)
    ├─ Request rate: 50x
    ├─ CPU: 40% → 90%
    ├─ Cache: under pressure
    └─ Calling product-catalog (amplifies load)
    
    checkout service (DOWNSTREAM #6)
    ├─ Request rate: 50x
    ├─ Calling: cart, payment, shipping, product-catalog
    ├─ CPU: 30% → 85%
    └─ Transaction volume spike

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+10min)                       │
└─────────────────────────────────────────────────────────────┘

🟠 Infrastructure Services:
    
    valkey-cart (DOWNSTREAM #7)
    ├─ Connection count: 10 → 200
    ├─ Command rate: 50x
    ├─ CPU: 15% → 60%
    └─ Memory: increases
    
    postgresql (DOWNSTREAM #8)
    ├─ Connection pool: nearly exhausted
    ├─ Query rate: 20x increase
    ├─ Disk I/O: spike
    ├─ Lock contention: increases
    └─ Slow query log fills up
    
    kafka (DOWNSTREAM #9)
    ├─ Message rate: 50x (from checkout)
    ├─ Broker CPU: increases
    ├─ Disk writes: spike
    └─ Consumer lag: may build up
    
🟡 Observability Stack (DOWNSTREAM #10)
    
    otel-collector
    ├─ Metric cardinality: spike
    ├─ Trace volume: 50x
    ├─ Memory: increases significantly
    └─ May start dropping data
    
    jaeger
    ├─ Trace storage: rapid growth
    ├─ Query performance: degraded
    └─ UI may become slow
    
    prometheus
    ├─ Scrape duration: increases
    ├─ Query performance: slower
    └─ TSDB memory: increases
    
    opensearch
    ├─ Log ingestion: 50x
    ├─ Index rate: spike
    ├─ Disk I/O: saturated
    └─ Query latency: increases

┌─────────────────────────────────────────────────────────────┐
│ TERTIARY IMPACT (T+5min to T+30min)                        │
└─────────────────────────────────────────────────────────────┘

🔴 Kubernetes/Node Level
    ├─ Node CPU: 40% → 90% (across all nodes)
    ├─ Node memory: pressure
    ├─ Network bandwidth: saturated
    ├─ Disk I/O: saturated
    └─ OOMKiller may activate

🔴 Cascade Failures (worst case)
    ├─ Service A: overloaded → fails
    ├─ Service B: cannot reach A → fails
    ├─ Service C: cannot reach B → fails
    └─ Cascading collapse

🟡 Auto-scaling (if enabled)
    ├─ HPA detects high CPU
    ├─ Pods scaling: 2 → 5 → 10
    ├─ Takes 2-5 minutes to stabilize
    └─ May not scale fast enough

🟠 Business Impact
    ├─ Legitimate users: cannot access site
    ├─ Service degradation: widespread
    ├─ Revenue loss: during incident
    └─ Reputation damage
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `frontend-proxy` | 🟠 Moderate | Connection pressure | Immediate |
| `frontend` | 🟠 Moderate | CPU 90%, latency 5x | 1-2 min |
| `ad` | 🟡 Minor | CPU 80%, latency 6x | 1 min |
| `cart` | 🟡 Minor | CPU 70%, cache pressure | 1 min |
| `product-catalog` | 🟠 Moderate | CPU 85%, DB pressure | 2 min |
| `recommendation` | 🟠 Moderate | CPU 90%, latency spike | 2 min |
| `checkout` | 🟠 Moderate | CPU 85%, multi-service | 2 min |
| `valkey-cart` | 🟡 Minor | Connection 20x | 1 min |
| `postgresql` | 🟠 Moderate | Connection pool 90% | 5 min |
| `kafka` | 🟡 Minor | Message rate 50x | 5-10 min |
| `otel-collector` | 🟡 Minor | Trace volume 50x | 2 min |
| `jaeger` | 🟡 Minor | Storage growth | 10 min |
| `prometheus` | 🟡 Minor | Query slow | 5 min |
| `opensearch` | 🟡 Minor | Log ingestion spike | 10 min |

### Detection Metrics

```promql
# Primary signal - request rate
sum(rate(http_server_requests_total[1m])) > 100

# Resource saturation
avg(rate(container_cpu_usage_seconds_total[1m])) > 0.8

# Latency degradation across all services
avg(histogram_quantile(0.95, 
  rate(http_server_duration_bucket[5m])
)) > 1.0

# Node pressure
node_cpu_usage_percent > 90
```

### Diagnosis Difficulty
🟢 **Easy** - Obvious traffic spike, all services affected, clear metrics

### Business Impact
💰 **High** - Site-wide degradation, legitimate user impact, potential downtime

### Characteristics
- **Widespread** - Affects ALL services
- **Rapid onset** - Immediate impact
- **Resource exhaustion** - Every layer affected
- **Simulates real scenarios** - DDoS, viral traffic, bot attack

---

## 11. LLM Rate Limit

### Trigger Command
```bash
./incidentfox/scripts/scenarios/llm-rate-limit.sh
```

### Failure Source
**Service:** `llm` (mock AI service)
**Failure Mode:** Returns rate limit errors (429)

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
llm service ❌ RATE LIMIT (429)
    │
    ├─ Intermittent 429 errors
    ├─ Rate: 20-50% of requests
    ├─ Simulates: OpenAI API rate limit
    └─ Error message: "Rate limit exceeded"
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+30s)                           │
└─────────────────────────────────────────────────────────────┘
    
🟡 product-reviews service (DOWNSTREAM #1)
    ├─ LLM call fails for product summary
    ├─ Fallback behavior triggered:
    │   └─ Option A: Return cached summary
    │   └─ Option B: Return "Summary unavailable"
    │   └─ Option C: Retry with backoff
    ├─ Some product reviews: incomplete
    └─ Error logs generated
    
    ↓
    
🟢 frontend service (DOWNSTREAM #2)
    ├─ Product review section: degraded
    ├─ Missing AI-generated summaries
    ├─ Raw reviews still displayed
    └─ Minor UX degradation
    
    User Experience:
    ├─ Product pages: mostly work
    ├─ AI summary: "Temporarily unavailable"
    ├─ Users can still read individual reviews
    └─ Minimal impact on purchase decisions

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+10min)                       │
└─────────────────────────────────────────────────────────────┘

🟡 product-reviews service
    ├─ Retry logic: increases load on LLM
    ├─ Exponential backoff: delays responses
    ├─ Cache hit rate: increases (using stale summaries)
    └─ Alert: "High LLM error rate"

🟢 Business Impact
    ├─ Feature degradation: not broken
    ├─ Revenue impact: minimal
    ├─ User experience: slightly degraded
    └─ SEO: not affected (reviews still visible)

🟡 Cost Impact
    ├─ Retry attempts: may increase LLM API costs
    ├─ Cached responses: reduce costs
    └─ Net: likely cost savings (fewer successful calls)
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `llm` | 🟡 Moderate | Rate limit errors (429) | Immediate (flag off) |
| `product-reviews` | 🟡 Minor | Fallback to cache | Immediate |
| `frontend` | 🟢 Minimal | Missing AI summaries | Immediate |
| `end-users` | 🟢 Minimal | Slightly degraded UX | Immediate |

### Detection Metrics

```promql
# Primary signal - rate limit errors
sum(rate(http_server_requests_total{
  service_name="llm",
  http_status_code="429"
}[5m])) > 5

# Downstream impact - fallback rate
rate(product_reviews_llm_fallback_total[5m]) > 10

# Error logs
rate(log_entries{service="product-reviews",level="error",message=~".*rate limit.*"}[5m])
```

### Diagnosis Difficulty
🟢 **Easy** - Clear HTTP 429 errors, obvious logs, graceful degradation

### Business Impact
💰 **Very Low** - Feature degradation only, non-critical, revenue impact minimal

### Characteristics
- **Graceful degradation** - Fallback to cache
- **Non-critical service** - AI summaries are "nice to have"
- **Intermittent** - Not all requests fail
- **Real-world scenario** - Common with third-party APIs

---

## 12. LLM Inaccuracy

### Trigger Command
```bash
./incidentfox/scripts/scenarios/llm-inaccuracy.sh
```

### Failure Source
**Service:** `llm` (mock AI service)
**Failure Mode:** Returns incorrect/nonsensical summaries

### Cascade Impact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INITIAL FAILURE                                             │
└─────────────────────────────────────────────────────────────┘
llm service ❌ INACCURATE RESPONSES
    │
    ├─ Returns HTTP 200 (success)
    ├─ But content is wrong/misleading
    ├─ Example: Product summary for telescope describes a toaster
    └─ Data quality issue, not performance issue
    
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ IMMEDIATE IMPACT (T+0s to T+30s)                           │
└─────────────────────────────────────────────────────────────┘
    
🟡 product-reviews service (DOWNSTREAM #1)
    ├─ Receives inaccurate LLM response
    ├─ No error detected (HTTP 200)
    ├─ Stores bad summary in cache
    ├─ Serves bad summary to frontend
    └─ No technical failure indicators
    
    ↓
    
🟠 frontend service (DOWNSTREAM #2)
    ├─ Displays incorrect product summary
    ├─ Users see misleading information
    ├─ Technical system: healthy
    └─ Quality assurance failure
    
    User Experience:
    ├─ Product page: loads fine
    ├─ AI summary: completely wrong
    ├─ Confusion about product
    ├─ May question site credibility
    └─ May abandon purchase

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY IMPACT (T+1min to T+1hour)                       │
└─────────────────────────────────────────────────────────────┘

🟠 User Trust
    ├─ Users notice wrong information
    ├─ Screenshot and share on social media
    ├─ "This site gave me wrong info" complaints
    └─ Brand reputation damage

🟡 Business Operations
    ├─ Customer support: receives complaints
    ├─ Social media team: damage control
    ├─ Product team: investigates
    └─ Manual review of AI outputs needed

🔴 Detection Challenges
    ├─ No technical error metrics
    ├─ All health checks: green
    ├─ Monitoring: shows healthy system
    ├─ Detection: requires human review or AI validation
    └─ May go unnoticed for hours/days

┌─────────────────────────────────────────────────────────────┐
│ LONG-TERM IMPACT (Hours to Days)                           │
└─────────────────────────────────────────────────────────────┘

🟠 Trust and Reputation
    ├─ Brand credibility: damaged
    ├─ User trust in AI features: reduced
    ├─ Media attention: possible
    └─ Competitor advantage

🟡 Remediation
    ├─ Disable AI summaries feature
    ├─ Manual review of all cached summaries
    ├─ Implement content validation
    └─ Add human-in-the-loop oversight
```

### Affected Services Summary

| Service | Impact Level | Impact Type | Recovery Time |
|---------|-------------|-------------|---------------|
| `llm` | 🟡 Moderate | Data quality issue | Immediate (flag off) + cache clear |
| `product-reviews` | 🟡 Minor | Serves bad data | Need cache invalidation |
| `frontend` | 🟠 Moderate | Shows wrong info | After cache clear |
| `end-users` | 🟠 Moderate | Misleading info, trust loss | Immediate + reputation |
| `business` | 🟠 Moderate | Brand damage, support load | Hours to days |

### Detection Metrics

```promql
# Difficult to detect with standard metrics!

# User reports (if instrumented)
rate(user_feedback_negative{page="product-reviews"}[1h]) > 10

# Content moderation flags (if implemented)
rate(content_validation_failed{source="llm"}[1h]) > 5

# Support tickets (if integrated)
rate(support_tickets{category="wrong_product_info"}[1h]) > 3
```

### Diagnosis Difficulty
🔴 **Very Hard** - No technical errors, requires content analysis, human detection

### Business Impact
💰 **Medium-High** - Trust loss, brand damage, potential legal issues, hard to detect

### Characteristics
- **No technical failure** - All systems green
- **Data quality issue** - Not a performance problem
- **Hard to detect** - Requires human review or AI validation
- **Reputation risk** - Can go viral on social media
- **Cascading trust impact** - Users question all AI features

### Why This Scenario is Special

This is the only "system healthy but data wrong" scenario:
- All services: healthy ✓
- All metrics: normal ✓
- All logs: clean ✓
- User experience: terrible ✗

Requires different detection and response strategies:
1. Content validation pipelines
2. Human review workflows
3. User feedback integration
4. A/B testing with human validation
5. AI output monitoring (AI monitoring AI)

---

## Summary: Failure Impact Comparison

| Failure Scenario | Initial Service | Downstream Count | Cascade Depth | Business Impact | Detection Difficulty | Recovery Time |
|---------|------------|----------|---------|---------|---------|---------|
| **Cache Failure** | recommendation | 3 | Medium | Low | Easy | Immediate |
| **Payment Failure (50%)** | payment | 6 | Medium | High | Easy | Immediate |
| **High CPU (Ad)** | ad | 2 | Low | Low | Very Easy | Immediate |
| **Memory Leak (Email)** | email | 3 | Low | Medium | Medium | Restart needed |
| **Latency Spike (Image)** | image-provider | 3 | Low | Medium | Easy | Immediate |
| **Kafka Lag** | kafka+consumers | 5 | High | Medium-High | Medium | 5-30 min |
| **Catalog Failure** | product-catalog | 5 | High | Critical | Easy | Immediate |
| **Payment Unreachable** | payment | 6 | Medium | Critical | Very Easy | Immediate |
| **Ad GC Pressure** | ad | 2 | Low | Low | Medium | Immediate |
| **Traffic Spike** | ALL | 14 | Very High | High | Easy | 2-10 min |
| **LLM Rate Limit** | llm | 3 | Low | Very Low | Easy | Immediate |
| **LLM Inaccuracy** | llm | 4 | Low | Medium-High | Very Hard | Cache clear |

## Cascade Depth Definitions

- **Low**: 1-2 layers of downstream impact
- **Medium**: 3-4 layers of downstream impact  
- **High**: 5-6 layers of downstream impact
- **Very High**: System-wide impact

## Best Demo Scenario Rankings

1. 🥇 **Cache Failure** - Perfect teaching example
2. 🥈 **Payment Failure (50%)** - Real business impact
3. 🥉 **Kafka Lag** - Complex async systems
4. **Catalog Failure** - Core service failure
5. **Traffic Spike** - Full system stress test

---

## Usage Recommendations

### For AI Agent Developers

**Learning Path (Easy to Hard):**

1. **Week 1**: `cache-failure`, `latency-spike`, `high-cpu`
   - Clear cause-effect relationships
   - Simple metric signals
   - Immediate recovery

2. **Week 2**: `service-failure`, `catalog-failure`, `payment-unreachable`
   - Business impact understanding
   - Multi-service coordination
   - Error propagation

3. **Week 3**: `kafka-lag`, `memory-leak`, `traffic-spike`
   - Async systems
   - Progressive failures
   - System-level impact

4. **Week 4**: `llm-inaccuracy`, `ad-gc-pressure`
   - Data quality issues
   - Intermittent failures
   - Advanced diagnosis

### For Demos and Training

**5-minute quick demo**: `cache-failure`
**15-minute deep dive**: `payment-failure` → fix → `kafka-lag`
**30-minute full workshop**: Progressive failures from `cache-failure` to `traffic-spike`

### For Testing AI Agent Capabilities

**Level 1 (Basic)**: Can detect and diagnose single-service failures
- `high-cpu`, `latency-spike`, `service-unreachable`

**Level 2 (Intermediate)**: Can trace cascading impacts
- `cache-failure`, `service-failure`, `catalog-failure`

**Level 3 (Advanced)**: Can handle complex async systems
- `kafka-lag`, `memory-leak`, `traffic-spike`

**Level 4 (Expert)**: Can discover non-technical failures
- `llm-inaccuracy`, `ad-gc-pressure`

---

## Document Version

- **Version**: 1.0
- **Last Updated**: 2024-12-11
- **Author**: IncidentFox Team
- **Based on**: OpenTelemetry Demo + IncidentFox Extensions
