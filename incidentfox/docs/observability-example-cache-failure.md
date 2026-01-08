# Observability Example: Cache Failure Scenario

## Overview

When you inject a **cache failure** using `./incidentfox/scripts/trigger-incident.sh cache-failure`, here's exactly what metrics, logs, and traces will show anomalies.

## Observability Endpoints

All accessible via Docker Compose (default) or Kubernetes:

```yaml
Prometheus:  http://localhost:9090
Grafana:     http://localhost:8080/grafana
Jaeger:      http://localhost:8080/jaeger/ui
OpenSearch:  http://localhost:9200
```

Full details: [`agent-config/endpoints.yaml`](../agent-config/endpoints.yaml)

---

## Timeline: Cache Failure Scenario

### T+0s: Trigger the Failure

```bash
./incidentfox/scripts/trigger-incident.sh cache-failure
```

This enables the `recommendationCacheFailure` feature flag, causing the recommendation service cache to fail.

---

## What You'll See in Observability Tools

### 1. Prometheus Metrics (T+0s to T+30s)

#### ✅ Primary Signals - Recommendation Service

**Query: Latency Spike**
```promql
histogram_quantile(0.95, 
  rate(http_server_duration_bucket{service_name="recommendation"}[5m])
)
```

**Before:**
```
Value: 0.050 (50ms)
```

**After (T+10s):**
```
Value: 0.520 (520ms)  ⬆️ 10x INCREASE
```

---

**Query: Cache Hit Rate**
```promql
recommendation_cache_hit_rate
```

**Before:**
```
Value: 0.94 (94% hit rate)
```

**After (T+5s):**
```
Value: 0.00 (0% hit rate)  ⬇️ DROPPED TO ZERO
```

---

**Query: CPU Usage**
```promql
rate(process_cpu_seconds_total{service_name="recommendation"}[1m])
```

**Before:**
```
Value: 0.20 (20% CPU)
```

**After (T+15s):**
```
Value: 0.60 (60% CPU)  ⬆️ 3x INCREASE
```

---

**Query: Request Rate to Product Catalog**
```promql
rate(http_client_requests_total{
  service_name="recommendation",
  target="product-catalog"
}[1m])
```

**Before:**
```
Value: 10 req/s
```

**After (T+10s):**
```
Value: 100 req/s  ⬆️ 10x INCREASE (cache bypass)
```

---

#### ✅ Secondary Signals - Product Catalog Service (Downstream)

**Query: Request Rate Received**
```promql
rate(http_server_requests_total{service_name="product-catalog"}[1m])
```

**Before:**
```
Value: 95 req/s
```

**After (T+60s):**
```
Value: 980 req/s  ⬆️ 10x INCREASE
```

---

**Query: CPU Usage**
```promql
rate(process_cpu_seconds_total{service_name="product-catalog"}[1m])
```

**Before:**
```
Value: 0.15 (15% CPU)
```

**After (T+60s):**
```
Value: 0.68 (68% CPU)  ⬆️ 4.5x INCREASE
```

---

**Query: Latency**
```promql
histogram_quantile(0.95,
  rate(http_server_duration_bucket{service_name="product-catalog"}[5m])
)
```

**Before:**
```
Value: 0.022 (22ms)
```

**After (T+60s):**
```
Value: 0.125 (125ms)  ⬆️ 5.7x INCREASE
```

---

#### ✅ Tertiary Signals - Frontend (End User Impact)

**Query: Page Load Time**
```promql
histogram_quantile(0.95,
  rate(http_server_duration_bucket{service_name="frontend"}[5m])
)
```

**Before:**
```
Value: 0.200 (200ms)
```

**After (T+60s):**
```
Value: 0.800 (800ms)  ⬆️ 4x INCREASE
```

---

### 2. Grafana Dashboards

#### Dashboard: "Demo Dashboard"
Location: `http://localhost:8080/grafana/d/demo`

**Panels showing anomalies:**

1. **Service Latency (P95)**
   - recommendation: 50ms → **520ms** 🔴
   - product-catalog: 22ms → **125ms** 🟡

2. **CPU Usage**
   - recommendation: 20% → **60%** 🟡
   - product-catalog: 15% → **68%** 🟡

3. **Request Rate**
   - product-catalog incoming: 95 → **980 req/s** 🟡

4. **Error Rate**
   - All services: 0% ✅ (no errors, just slow)

---

### 3. Logs - OpenSearch

#### Query 1: Recommendation Service Errors

**API Call:**
```bash
curl -X POST "http://localhost:9200/logs-*/_search" -H 'Content-Type: application/json' -d '{
  "query": {
    "bool": {
      "must": [
        {"term": {"service.name": "recommendation"}},
        {"match": {"message": "cache"}},
        {"range": {"@timestamp": {"gte": "now-5m"}}}
      ]
    }
  },
  "size": 10,
  "sort": [{"@timestamp": "desc"}]
}'
```

**Expected Logs:**

```json
{
  "@timestamp": "2024-12-11T14:30:05Z",
  "service.name": "recommendation",
  "severity": "ERROR",
  "message": "CacheConnectionException: Connection refused to redis:6379",
  "trace_id": "a1b2c3d4e5f6...",
  "span_id": "x7y8z9..."
}
```

```json
{
  "@timestamp": "2024-12-11T14:30:06Z",
  "service.name": "recommendation",
  "severity": "WARN",
  "message": "Cache unavailable, falling back to direct catalog queries",
  "cache_hit_rate": 0.0
}
```

```json
{
  "@timestamp": "2024-12-11T14:30:10Z",
  "service.name": "recommendation",
  "severity": "INFO",
  "message": "Cache connection attempts failing: 25 consecutive failures"
}
```

---

#### Query 2: Product Catalog High Load

```bash
curl -X POST "http://localhost:9200/logs-*/_search" -H 'Content-Type: application/json' -d '{
  "query": {
    "bool": {
      "must": [
        {"term": {"service.name": "product-catalog"}},
        {"range": {"@timestamp": {"gte": "now-5m"}}}
      ]
    }
  },
  "size": 10
}'
```

**Expected Logs:**

```json
{
  "@timestamp": "2024-12-11T14:31:05Z",
  "service.name": "product-catalog",
  "severity": "WARN",
  "message": "Database connection pool pressure: 45/50 connections in use",
  "db_pool_usage": 0.90
}
```

```json
{
  "@timestamp": "2024-12-11T14:31:10Z",
  "service.name": "product-catalog",
  "severity": "INFO",
  "message": "High request rate detected: 980 req/s (baseline: 95 req/s)",
  "request_rate": 980
}
```

---

### 4. Traces - Jaeger

#### Access Jaeger UI:
```
http://localhost:8080/jaeger/ui
```

#### Search for Traces:

**Query 1: Recommendation Service Slow Traces**

```
Service: recommendation
Min Duration: 500ms
Limit: 20
```

**What You'll See:**

**Before failure:**
```
Trace ID: abc123...
Duration: 52ms
Spans:
  └─ recommendation.GetRecommendations (52ms)
     ├─ cache.Get (2ms) ✅ Cache hit
     └─ (no product-catalog call)
```

**After failure (T+10s):**
```
Trace ID: def456...
Duration: 525ms  🔴 10x SLOWER
Spans:
  └─ recommendation.GetRecommendations (525ms)
     ├─ cache.Get (2ms) ❌ Cache miss
     └─ product-catalog.ListProducts (498ms)  ⬅️ NEW! (cache bypass)
        └─ postgresql.Query (485ms)
```

**Key Observation:** Trace now shows extra hop to product-catalog (wasn't there before)

---

**Query 2: Frontend Traces (Showing Cascade)**

```
Service: frontend
Operation: GET /product/{id}
Min Duration: 300ms
```

**After failure (T+60s):**
```
Trace ID: ghi789...
Duration: 820ms  🔴 4x SLOWER
Spans:
  └─ frontend.GetProduct (820ms)
     ├─ recommendation.GetRecommendations (525ms)  🔴 SLOW
     │  └─ product-catalog.ListProducts (498ms)  ⬅️ Bottleneck
     │     └─ postgresql.Query (485ms)
     ├─ product-catalog.GetProduct (85ms)  🟡 Slower than normal
     ├─ ad.GetAd (42ms) ✅ Normal
     └─ cart.GetCart (18ms) ✅ Normal
```

**Key Observation:** 
- recommendation span is now the bottleneck
- product-catalog appears twice (recommendation + frontend direct call)
- Overall request 4x slower due to recommendation latency

---

**Query 3: Error Traces (if any)**

```
Service: recommendation
Tags: error:true
```

**Might see:**
```
Trace ID: jkl012...
Status: Error
Error message: "Cache connection timeout"
Spans:
  └─ recommendation.GetRecommendations (ERROR)
     └─ cache.Get (ERROR: Connection timeout after 5s)
```

---

### 5. Full Example: Correlation Across Tools

#### T+30s After Injection:

**Prometheus shows:**
```
recommendation P95 latency: 520ms (was 50ms)
recommendation cache hit rate: 0% (was 94%)
recommendation CPU: 60% (was 20%)
product-catalog request rate: 980 req/s (was 95 req/s)
product-catalog CPU: 68% (was 15%)
```

**Grafana Dashboard shows:**
- 🔴 Red spike in recommendation latency panel
- 🟡 Yellow spike in product-catalog CPU panel
- 📈 Request rate graph shows 10x jump

**Logs show:**
```
[ERROR] recommendation: CacheConnectionException: Connection refused
[WARN] recommendation: Cache unavailable, falling back to direct queries
[WARN] product-catalog: High request rate: 980 req/s
[WARN] product-catalog: DB connection pool pressure: 90%
```

**Traces show:**
- Slow traces (500ms+) for recommendation service
- Extra spans: recommendation → product-catalog (not present before)
- product-catalog spans under high load (slower than baseline)

---

## How to Detect This As An AI Agent

### Detection Algorithm:

1. **Primary Signal** (Prometheus):
   ```python
   # Check recommendation latency
   latency = query_prometheus(
       "histogram_quantile(0.95, rate(http_server_duration_bucket{service_name='recommendation'}[5m]))"
   )
   
   if latency > 0.5:  # 500ms threshold
       alert("High latency detected in recommendation service")
   ```

2. **Root Cause Analysis** (Prometheus):
   ```python
   # Check cache hit rate
   cache_hit_rate = query_prometheus("recommendation_cache_hit_rate")
   
   if cache_hit_rate < 0.1:  # Below 10%
       root_cause = "Cache failure or unavailable"
   ```

3. **Downstream Impact** (Prometheus):
   ```python
   # Check product-catalog load
   catalog_rps = query_prometheus(
       "rate(http_server_requests_total{service_name='product-catalog'}[1m])"
   )
   
   if catalog_rps > 500:  # Baseline is ~95
       downstream_impact = "product-catalog receiving excessive traffic"
   ```

4. **Correlate with Logs** (OpenSearch):
   ```python
   logs = query_opensearch({
       "query": {
           "bool": {
               "must": [
                   {"term": {"service.name": "recommendation"}},
                   {"match": {"message": "cache"}}
               ]
           }
       }
   })
   
   if "CacheConnectionException" in logs:
       confirm("Cache connection failure")
   ```

5. **Verify with Traces** (Jaeger):
   ```python
   traces = query_jaeger(service="recommendation", minDuration="500ms")
   
   for trace in traces:
       if has_span(trace, target="product-catalog"):
           # Recommendation is calling catalog (cache bypass)
           confirm("Cache miss forcing direct catalog calls")
   ```

---

## Complete Anomaly Signature: Cache Failure

### Metrics Anomalies:

| Metric | Service | Normal | During Failure | Change |
|--------|---------|--------|----------------|--------|
| P95 Latency | recommendation | 50ms | 520ms | **10x ⬆️** |
| Cache Hit Rate | recommendation | 94% | 0% | **⬇️ ZERO** |
| CPU Usage | recommendation | 20% | 60% | **3x ⬆️** |
| Request Rate | product-catalog | 95/s | 980/s | **10x ⬆️** |
| CPU Usage | product-catalog | 15% | 68% | **4.5x ⬆️** |
| P95 Latency | product-catalog | 22ms | 125ms | **5.7x ⬆️** |
| Page Load Time | frontend | 200ms | 800ms | **4x ⬆️** |

### Log Patterns:

**Recommendation Service:**
```
[ERROR] CacheConnectionException: Connection refused to redis:6379
[WARN] Cache unavailable, falling back to direct catalog queries  
[INFO] Cache connection attempts failing: X consecutive failures
[ERROR] Redis pool exhausted
```

**Product Catalog Service:**
```
[WARN] High request rate detected: 980 req/s
[WARN] Database connection pool pressure: 90%
[INFO] Serving 10x normal traffic
```

### Trace Patterns:

**Before (Normal):**
```
frontend (200ms)
  └─ recommendation (45ms)
     └─ cache.Get (2ms) ✅
```

**After (Cache Failure):**
```
frontend (820ms)  🔴 4x slower
  └─ recommendation (525ms)  🔴 10x slower
     ├─ cache.Get (2ms) ❌ Miss
     └─ product-catalog.ListProducts (498ms)  ⬅️ NEW SPAN!
        └─ postgresql.Query (485ms)
```

**Key Trace Indicators:**
- ✅ New span appears: `recommendation → product-catalog`
- ✅ `cache.Get` span present but returns miss
- ✅ Overall trace duration 4-10x longer
- ✅ product-catalog spans under higher load

---

## API Examples: Querying the Data

### Prometheus API

**Check Latency:**
```bash
curl "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_server_duration_bucket{service_name=\"recommendation\"}[5m]))"
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {"service_name": "recommendation"},
        "value": [1702311000, "0.520"]  ⬅️ 520ms
      }
    ]
  }
}
```

---

**Check Cache Hit Rate:**
```bash
curl "http://localhost:9090/api/v1/query?query=recommendation_cache_hit_rate"
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "result": [
      {
        "metric": {"service_name": "recommendation"},
        "value": [1702311000, "0.0"]  ⬅️ 0% hit rate
      }
    ]
  }
}
```

---

### Jaeger API

**Find Slow Traces:**
```bash
curl "http://localhost:16686/api/traces?service=recommendation&minDuration=500ms&limit=10"
```

**Response:**
```json
{
  "data": [
    {
      "traceID": "a1b2c3d4e5f6...",
      "spans": [
        {
          "spanID": "span1",
          "operationName": "recommendation.GetRecommendations",
          "duration": 525000,
          "tags": [
            {"key": "cache.hit", "value": false},
            {"key": "cache.miss.reason", "value": "connection_error"}
          ]
        },
        {
          "spanID": "span2",
          "parentSpanID": "span1",
          "operationName": "product-catalog.ListProducts",
          "duration": 498000,
          "references": [{"refType": "CHILD_OF", "spanID": "span1"}]
        }
      ]
    }
  ]
}
```

**Key Fields:**
- `duration`: 525ms (vs baseline ~50ms)
- `tags.cache.hit`: false
- New child span to `product-catalog`

---

### OpenSearch API

**Search Logs:**
```bash
curl -X POST "http://localhost:9200/logs-*/_search" -H 'Content-Type: application/json' -d '{
  "query": {
    "bool": {
      "must": [
        {"term": {"service.name": "recommendation"}},
        {"match": {"severity": "ERROR"}},
        {"range": {"@timestamp": {"gte": "now-5m"}}}
      ]
    }
  },
  "size": 100,
  "sort": [{"@timestamp": "desc"}]
}'
```

**Response:**
```json
{
  "hits": {
    "total": {"value": 45},
    "hits": [
      {
        "_source": {
          "@timestamp": "2024-12-11T14:30:05.123Z",
          "service.name": "recommendation",
          "severity": "ERROR",
          "body": "CacheConnectionException: Connection refused to redis:6379",
          "trace_id": "a1b2c3d4e5f6...",
          "span_id": "x7y8z9...",
          "attributes": {
            "error.type": "CacheConnectionException",
            "redis.host": "redis",
            "redis.port": 6379
          }
        }
      }
    ]
  }
}
```

---

## Complete Detection Flow

### Step 1: Detect Anomaly (Prometheus)
```python
# Monitor latency
latency = prometheus.query("recommendation P95 latency")
if latency > 500ms:
    incident = create_incident("High latency in recommendation")
```

### Step 2: Identify Root Cause (Prometheus + Logs)
```python
# Check cache metrics
cache_hit_rate = prometheus.query("recommendation_cache_hit_rate")
if cache_hit_rate < 0.1:
    root_cause = "Cache failure"
    
# Confirm with logs
logs = opensearch.search("recommendation", "cache", "ERROR")
if "CacheConnectionException" in logs:
    confirmed = True
```

### Step 3: Assess Impact (Prometheus + Traces)
```python
# Check downstream services
catalog_load = prometheus.query("product-catalog request rate")
if catalog_load > 500:
    downstream_impact = ["product-catalog"]
    
# Verify with traces
traces = jaeger.search(service="recommendation", minDuration="500ms")
for trace in traces:
    if "product-catalog" in trace.spans:
        cascade_confirmed = True
```

### Step 4: Determine Severity
```python
severity = calculate_severity(
    latency=10x,
    services_affected=2,
    user_impact="degraded",
    error_rate=0
)
# Result: SEV-3 (Degraded performance, no errors, limited scope)
```

### Step 5: Remediate
```python
# Check feature flags
flag_status = flagd.get("recommendationCacheFailure")
if flag_status == "enabled":
    flagd.set("recommendationCacheFailure", "off")
    
# Verify recovery
wait(30)
latency = prometheus.query("recommendation P95 latency")
if latency < 100ms:
    incident.resolve("Cache failure flag disabled")
```

---

## Key Metrics to Monitor Per Scenario

### Cache Failure:
- ✅ `recommendation_cache_hit_rate` → 0%
- ✅ `recommendation P95 latency` → 10x
- ✅ `product-catalog request rate` → 10x
- ✅ Traces: new `recommendation → product-catalog` spans

### Payment Failure:
- ✅ `payment error rate` → 50%
- ✅ `checkout error rate` → 50%
- ✅ `http_status_code="500"` → increase
- ✅ Logs: "Payment processing failed"

### Kafka Lag:
- ✅ `kafka_consumer_lag{topic="orders"}` → 1000+
- ✅ `accounting last_processed_time` → 8 min ago
- ✅ `fraud_detection_delay` → 8 min
- ✅ Logs: "Consumer lag detected"

### High CPU:
- ✅ `process_cpu_seconds_total{service="ad"}` → 0.95 (95%)
- ✅ `http_server_duration{service="ad"}` → 10x
- ✅ `http_server_requests_active{service="ad"}` → 100+ (queue)
- ✅ Logs: "Thread pool exhausted"

---

## Pre-built Grafana Dashboards

Access: `http://localhost:8080/grafana`

### 1. **Demo Dashboard**
- Overall system health
- Service latency (all services)
- Request rates
- Error rates

### 2. **Span Metrics Dashboard**
- Trace-derived metrics
- Service dependencies (auto-discovered)
- Operation latencies
- Error traces

### 3. **Service-Specific Dashboards**
- Per-service CPU/Memory/Latency
- Request throughput
- Error rates
- Custom service metrics

---

## Testing Your Detection

### Quick Test:

```bash
# 1. Start monitoring (before failure)
curl "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_server_duration_bucket{service_name=\"recommendation\"}[5m]))" | jq '.data.result[0].value[1]'
# Output: "0.050" (50ms)

# 2. Inject failure
./incidentfox/scripts/trigger-incident.sh cache-failure

# 3. Wait 30 seconds
sleep 30

# 4. Check again
curl "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_server_duration_bucket{service_name=\"recommendation\"}[5m]))" | jq '.data.result[0].value[1]'
# Output: "0.520" (520ms) ⬆️ 10x INCREASE

# 5. Check cache
curl "http://localhost:9090/api/v1/query?query=recommendation_cache_hit_rate" | jq '.data.result[0].value[1]'
# Output: "0.0" (0%) ⬇️ DROPPED TO ZERO
```

---

## Summary: What Shows Anomalies

### ✅ Metrics (Prometheus):
- Latency increases (10x)
- Cache hit rate drops (0%)
- CPU increases (3x)
- Request rate to downstream increases (10x)

### ✅ Logs (OpenSearch):
- ERROR: "CacheConnectionException"
- WARN: "Cache unavailable, falling back"
- INFO: "High request rate detected"

### ✅ Traces (Jaeger):
- Trace duration 10x longer
- New spans appear (cache bypass)
- Downstream service spans under load

### ✅ Dashboards (Grafana):
- Visual spikes in latency panels
- CPU/Memory increases
- Request rate jumps

**All tools show correlated anomalies at the same time!** 🎯

---

## Additional Resources

- **Complete endpoint docs**: `agent-config/endpoints.yaml`
- **Query examples**: `docs/agent-integration.md`
- **All failure scenarios**: `docs/incident-scenarios.md`
- **Cascade analysis**: `docs/cascade-impact-analysis.md`

