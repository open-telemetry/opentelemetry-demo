# Failure Simulator

This document describes the failure simulation capabilities for testing the predictive alerts and root cause monitoring system.

## Quick Start

```bash
# Simulate slow database queries (detectable by root cause monitoring)
./scripts/simulate_failure.sh degrade postgres slow

# Inject 50% payment failures via otel-demo API
./scripts/simulate_failure.sh inject payment-failure 50%

# Restore everything
./scripts/simulate_failure.sh restore postgres
./scripts/simulate_failure.sh inject payment-failure off
```

## Failure Types and Detection

### Infrastructure Degradation (Detectable)

These failures produce **telemetry patterns** that root cause monitoring can detect:

| Command | What It Does | Expected Alert Type |
|---------|--------------|---------------------|
| `degrade postgres slow` | Adds 100-500ms delay to queries | `DB_SLOW_QUERIES` |
| `degrade postgres memory` | Reduces PostgreSQL memory settings | `DB_SLOW_QUERIES` (queries run slower) |

### Infrastructure Failures (Hard to Detect)

These failures **stop telemetry** rather than degrading it - they may only show up as `SERVICE_DOWN`:

| Command | What It Does | Expected Alert Type |
|---------|--------------|---------------------|
| `block postgres` | Revoke all DB connections | `DB_CONNECTION_FAILURE`, `SERVICE_DOWN` |
| `block redis` | Pause Redis container | `SERVICE_DOWN` (for services using Redis) |
| `block <service>` | Stop any docker service | `SERVICE_DOWN` |

### Application Failures via otel-demo API

These inject failures at the application level, producing rich telemetry:

| Command | What It Does | Expected Alert Type |
|---------|--------------|---------------------|
| `inject payment-failure 50%` | 50% of payments fail | `DEPENDENCY_FAILURE`, `ERROR_SPIKE` |
| `inject slow-images 5sec` | Images load slowly | `LATENCY_DEGRADATION`, `DEPENDENCY_LATENCY` |
| `inject cart-failure on` | Cart service fails | `DEPENDENCY_FAILURE`, `EXCEPTION_SURGE` |
| `inject ad-failure on` | Ad service fails | `DEPENDENCY_FAILURE` |
| `inject memory-leak 100x` | Recommendation service memory leak | `LATENCY_DEGRADATION` (as memory fills) |
| `inject kafka-problems on` | Kafka queue issues | `THROUGHPUT_DROP`, `LATENCY_DEGRADATION` |
| `inject recommendation-cache on` | Cache failures | `DEPENDENCY_FAILURE`, `LATENCY_DEGRADATION` |
| `inject product-failure on` | Product catalog fails | `DEPENDENCY_FAILURE`, `ERROR_SPIKE` |

## Detailed Usage

### PostgreSQL Degradation

```bash
# Slow queries (injects latency via TCP proxy)
./scripts/simulate_failure.sh degrade postgres slow

# Custom latency (default is 150ms)
PG_PROXY_LATENCY_MS=300 ./scripts/simulate_failure.sh degrade postgres slow

# Memory pressure (reduces work_mem to force disk-based sorts)
./scripts/simulate_failure.sh degrade postgres memory

# Check status (shows proxy state and measures actual query latency)
./scripts/simulate_failure.sh status postgres

# Restore to normal (removes proxy, restores direct connection)
./scripts/simulate_failure.sh restore postgres
```

**How `degrade postgres slow` works:**

Uses a **TCP proxy** (`alpine/socat`) to intercept PostgreSQL connections:

1. Disconnects PostgreSQL from the Docker network
2. Reconnects it with alias `postgresql-direct`
3. Starts a `socat` proxy container with alias `postgresql` (takes over the DNS name)
4. Adds `tc netem` latency on the proxy container (not PostgreSQL itself)
5. All services now connect through: **service → proxy (150ms delay) → postgresql**

Benefits over `tc` on PostgreSQL directly:
- `docker exec` into PostgreSQL still works normally
- `docker compose` commands don't hang
- Latency is configurable via `PG_PROXY_LATENCY_MS` env var
- PostgreSQL container is untouched

Run `restore postgres` to remove the proxy and restore direct connections.

### otel-demo API Injection

```bash
# Payment failures with different percentages
./scripts/simulate_failure.sh inject payment-failure 10%
./scripts/simulate_failure.sh inject payment-failure 50%
./scripts/simulate_failure.sh inject payment-failure 100%
./scripts/simulate_failure.sh inject payment-failure off

# Slow image loading
./scripts/simulate_failure.sh inject slow-images 5sec
./scripts/simulate_failure.sh inject slow-images 10sec
./scripts/simulate_failure.sh inject slow-images off

# Memory leak (multiplier)
./scripts/simulate_failure.sh inject memory-leak 10x
./scripts/simulate_failure.sh inject memory-leak 100x
./scripts/simulate_failure.sh inject memory-leak off

# Check all active feature flags
./scripts/simulate_failure.sh inject status
```

### Environment Variables

```bash
# Set otel-demo host (default: localhost)
export OTEL_DEMO_HOST=otel-demo.example.com

# Set otel-demo port (default: 8080)
export OTEL_DEMO_PORT=8080

# Set PostgreSQL database name (default: otel)
export POSTGRES_DB=otel
```

## Root Cause vs Symptom Detection

The predictive alerts system distinguishes between:

### Root Cause Alerts (Proactive)
Detect underlying issues before they impact users:
- `DB_CONNECTION_FAILURE` - Database connection/query errors
- `DB_SLOW_QUERIES` - Database query performance degradation
- `DEPENDENCY_FAILURE` - Downstream service call failures
- `DEPENDENCY_LATENCY` - Downstream service slow responses
- `EXCEPTION_SURGE` - Unusual increase in exceptions
- `NEW_EXCEPTION_TYPE` - Previously unseen exception types

### Symptom Alerts (Reactive)
Detect user-facing issues:
- `ERROR_SPIKE` - Increased error rate
- `LATENCY_DEGRADATION` - Slower response times
- `THROUGHPUT_DROP` - Reduced request volume
- `SERVICE_DOWN` - No telemetry received

## Testing Workflow

1. **Establish baselines** (wait 1-2 hours after starting the system)
2. **Inject a failure**:
   ```bash
   ./scripts/simulate_failure.sh degrade postgres slow
   ```
3. **Wait 2-3 minutes** for detection cycle
4. **Check Predictive Alerts page** - should show `DB_SLOW_QUERIES` alert
5. **Restore normal operation**:
   ```bash
   ./scripts/simulate_failure.sh restore postgres
   ```
6. **Wait for auto-resolution** - alert should auto-resolve in 15-30 minutes

## otel-demo Feature Flags (Reference)

Full list of available feature flags in the otel-demo application:

| Method Name | Action | Available Options |
|:---|:---|:---|
| `adFailure` | Fail ad service | `off`, `on` |
| `adHighCpu` | Triggers high cpu load in the ad service | `off`, `on` |
| `adManualGc` | Triggers full manual garbage collections in the ad service | `off`, `on` |
| `cartFailure` | Fail cart service | `off`, `on` |
| `emailMemoryLeak` | Memory leak in the email service | `off`, `1x`, `10x`, `100x`, `1000x`, `10000x` |
| `failedReadinessProbe` | Readiness probe failure for cart service | `off`, `on` |
| `imageSlowLoad` | Slow loading images in the frontend | `off`, `5sec`, `10sec` |
| `kafkaQueueProblems` | Overloads Kafka queue + consumer delay | `off`, `on` |
| `llmInaccurateResponse` | LLM returns an inaccurate product summary (ID L9ECAV7KIM) | `off`, `on` |
| `llmRateLimitError` | LLM intermittently returns a rate limit error | `off`, `on` |
| `loadGeneratorFloodHomepage` | Flood the frontend with a large amount of requests | `off`, `on` |
| `paymentFailure` | Fail payment service charge requests n% | `off`, `10%`, `25%`, `50%`, `75%`, `90%`, `100%` |
| `paymentUnreachable` | Payment service is unavailable | `off`, `on` |
| `productCatalogFailure` | Fail product catalog service on a specific product | `off`, `on` |
| `recommendationCacheFailure` | Fail recommendation service cache | `off`, `on` |
