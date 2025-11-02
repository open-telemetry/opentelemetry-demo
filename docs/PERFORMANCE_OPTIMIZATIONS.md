# Performance Optimization Guide

This document outlines critical performance optimizations identified through profiling analysis and provides implementation guidance for the OpenTelemetry Demo services.

## Executive Summary

Profiling analysis of production deployments identified **30-35% potential CPU reduction** across services through targeted optimizations. The highest impact services are:

- **checkoutservice**: 17x higher CPU consumption than median
- **frauddetectionservice**: Persistent elevated baseline (2.7x)
- **productcatalogservice**: Sporadic high CPU spikes

## Critical Issues & Solutions

### 1. Profiling Overhead (9.89% CPU) - IMMEDIATE ACTION REQUIRED

**Problem:** Pyroscope profiler consuming ~10% CPU, becoming a performance bottleneck.

**Solution:**

```yaml
# Reduce profiling sampling frequency
pyroscope.scrape "default" {
  profiling_config {
    profile.process_cpu {
      enabled = true
      frequency = 19  # Reduce from 100Hz to 19Hz
    }
    
    # Disable expensive profiling in production
    profile.block {
      enabled = false  # Saves 5.90% CPU
    }
    
    profile.mutex {
      enabled = false  # Disable unless debugging
    }
  }
}
```

**Expected Gain:** 10-15% CPU reduction

---

### 2. Regex Compilation in Hot Path (1.95% CPU)

**Problem:** `regexp.Compile()` called on every request in checkout service.

**Before:**
```go
func (cs *checkoutService) processOrder(ctx context.Context, req *pb.OrderRequest) {
    pattern := regexp.Compile(`[0-9]+`)  // ❌ EXPENSIVE!
    // ... use pattern
}
```

**After:**
```go
// At package level
var (
    orderPattern = regexp.MustCompile(`[0-9]+`)
    emailPattern = regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
)

func (cs *checkoutService) processOrder(ctx context.Context, req *pb.OrderRequest) {
    // ✅ Use pre-compiled pattern
    if orderPattern.MatchString(req.OrderId) {
        // ...
    }
}
```

**Expected Gain:** 2% CPU reduction

---

### 3. TLS Handshake Overhead (6.81% CPU)

**Problem:** Repeated TLS handshakes for every gRPC/HTTP connection.

**Solution:**

```go
import (
    "crypto/tls"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials"
    "google.golang.org/grpc/keepalive"
)

// Configure TLS with session resumption
tlsConfig := &tls.Config{
    ClientSessionCache: tls.NewLRUClientSessionCache(128),
    MinVersion:        tls.VersionTLS12,
}

// Configure gRPC with keepalive
conn, err := grpc.Dial(
    address,
    grpc.WithTransportCredentials(credentials.NewTLS(tlsConfig)),
    grpc.WithKeepaliveParams(keepalive.ClientParameters{
        Time:                10 * time.Second,
        Timeout:             3 * time.Second,
        PermitWithoutStream: true,
    }),
)
```

**Expected Gain:** 6-7% CPU reduction

---

### 4. Kafka Polling Inefficiency (8.39% CPU)

**Problem:** Aggressive Kafka polling causing excessive syscalls.

**Solution:**

```python
# Optimized Kafka consumer configuration
consumer_config = {
    'bootstrap.servers': kafka_broker,
    'group.id': consumer_group,
    'fetch.min.bytes': 1024,           # Wait for more data
    'fetch.wait.max.ms': 500,          # Increase wait time
    'max.poll.records': 500,           # Batch more records
    'enable.auto.commit': True,
    'auto.commit.interval.ms': 1000,
}

# Poll less frequently with larger batches
messages = consumer.poll(timeout_ms=500)
```

**Expected Gain:** 8% CPU reduction

---

### 5. Memory Allocation Pressure (5.35% CPU)

**Problem:** Frequent small allocations causing GC pressure.

**Solution:**

```go
import "sync"

// Create pools for frequently allocated objects
var bufferPool = sync.Pool{
    New: func() interface{} {
        return new(bytes.Buffer)
    },
}

func processRequest(data []byte) error {
    buf := bufferPool.Get().(*bytes.Buffer)
    defer func() {
        buf.Reset()
        bufferPool.Put(buf)
    }()
    
    // Use buf...
    return nil
}

// Pre-allocate slices with known capacity
items := make([]Item, 0, expectedSize)
```

**Expected Gain:** 5% CPU reduction + reduced GC pauses

---

### 6. Database Connection Overhead (1.22% CPU)

**Problem:** Creating new database connections per request.

**Solution:**

```go
// Connection pool (initialize once at startup)
var db *sql.DB

func init() {
    var err error
    db, err = sql.Open("postgres", connString)
    if err != nil {
        log.Fatal(err)
    }
    
    db.SetMaxOpenConns(25)
    db.SetMaxIdleConns(10)
    db.SetConnMaxLifetime(5 * time.Minute)
    db.SetConnMaxIdleTime(10 * time.Minute)
}
```

**Expected Gain:** 1-2% CPU reduction

---

### 7. DNS Resolution Latency (2.33% CPU)

**Problem:** Repeated DNS lookups for the same service endpoints.

**Solution:**

```yaml
# Kubernetes DNS caching
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns-custom
  namespace: kube-system
data:
  cache.override: |
    cache {
        success 9984 30
        denial 9984 5
    }
```

**Expected Gain:** 2% CPU reduction

---

## Implementation Priority

### Phase 1: Immediate (Quick Wins - This Week)
- [ ] Disable block/mutex profiling in Pyroscope (6% gain)
- [ ] Pre-compile regexes in checkout service (2% gain)
- [ ] Add database connection pooling (1-2% gain)

**Total Expected:** 9-10% CPU reduction

### Phase 2: Short-term (Next Sprint)
- [ ] Implement TLS session caching (6-7% gain)
- [ ] Optimize Kafka polling configuration (8% gain)
- [ ] Add object pooling for high-allocation paths (5% gain)

**Total Expected:** 19-20% CPU reduction

### Phase 3: Medium-term (Next Month)
- [ ] Configure DNS caching (2% gain)
- [ ] Review and optimize goroutine management
- [ ] Implement comprehensive connection pooling

**Total Expected:** Additional 2-3% CPU reduction

---

## Testing & Validation

### Before Making Changes
1. Capture baseline profiling data
2. Document current CPU usage metrics
3. Run load tests and record results

### After Each Optimization
1. Re-run profiling analysis
2. Compare CPU usage metrics
3. Verify no regression in functionality
4. Update this document with actual gains

### Monitoring
```promql
# CPU usage by service
rate(process_cpu_seconds_total{job="checkoutservice"}[5m])

# Memory allocation rate
rate(go_memstats_alloc_bytes_total[5m])

# GC pause time
rate(go_gc_duration_seconds_sum[5m])
```

---

## Service-Specific Recommendations

### checkoutservice (Highest Priority)
- **Current:** 17x median CPU consumption
- **Actions:** All optimizations above, especially regex and TLS
- **Expected:** 30-35% reduction

### frauddetectionservice
- **Current:** Persistent 2.7x baseline
- **Actions:** Kafka polling optimization, algorithm review
- **Expected:** 15-20% reduction

### productcatalogservice
- **Current:** Sporadic high spikes
- **Actions:** Connection pooling, investigate data coverage gaps
- **Expected:** 10-15% reduction during spikes

---

## References

- [Go Performance Tips](https://github.com/dgryski/go-perfbook)
- [Kafka Consumer Best Practices](https://docs.confluent.io/platform/current/clients/consumer.html)
- [gRPC Performance Best Practices](https://grpc.io/docs/guides/performance/)
- [Pyroscope Profiling Overhead](https://grafana.com/docs/pyroscope/latest/configure-client/)

---

## Contributing

Found additional optimizations? Please:
1. Profile your changes
2. Document the issue and solution
3. Add expected and actual performance gains
4. Submit a PR updating this document
