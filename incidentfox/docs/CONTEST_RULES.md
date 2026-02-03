# IncidentFox Root Cause Challenge

Welcome to the IncidentFox Root Cause Challenge! You'll investigate real incidents in a production-like microservices environment using multiple observability tools - just like a real SRE or on-call engineer.

---

## Quick Links

| Resource | URL | Purpose |
|----------|-----|---------|
| **Demo Application** | http://a06d7f5e0e0c949aebbaba8fb471d596-1428151517.us-west-2.elb.amazonaws.com:8080 | The e-commerce store |
| **Grafana** (Logs + Dashboards) | http://k8s-oteldemo-grafanap-6f80336927-c3991b69b6e4352a.elb.us-west-2.amazonaws.com/grafana | Logs (Loki) & Dashboards |
| **Jaeger** (Traces) | http://k8s-oteldemo-jaegerpu-ddab1a4609-a8c87825ebcf8ab1.elb.us-west-2.amazonaws.com | Distributed tracing |
| **Prometheus** (Metrics) | http://k8s-oteldemo-promethe-3a69e57319-21477e674196d46e.elb.us-west-2.amazonaws.com | Raw metrics & PromQL |

> **All telemetry systems are read-only and require no login.**

---

## Contest Rules

### Objective

When an incident is announced, your goal is to:
1. **Identify** the failing service/component
2. **Find the root cause** of the failure
3. **Provide evidence** from the telemetry systems (screenshots, trace IDs, log snippets)
4. **Submit your findings** in the designated Slack channel

### Scoring

| Criteria | Points |
|----------|--------|
| Correct root cause identification | 40 pts |
| Quality of evidence provided | 30 pts |
| Speed (first 3 correct submissions get bonus) | 20 pts |
| Clarity of explanation | 10 pts |

### Submission Format

```
## Root Cause Analysis

**Affected Service:** [service name]
**Root Cause:** [1-2 sentence description]

**Evidence:**
1. [Screenshot/link to Jaeger trace showing error]
2. [Screenshot/link to Grafana logs with error message]
3. [Prometheus query showing metric anomaly]

**Timeline:**
- HH:MM - First error observed in [system]
- HH:MM - Traced to [service]
- HH:MM - Root cause identified as [cause]
```

### Rules

1. **No attacking or modifying the systems** - read-only access only
2. **Work individually** - no team submissions
3. **Cite your evidence** - claims without proof don't count
4. **Be respectful** - this is a learning experience

---

## The Application: Telescope E-Commerce Store

This is an OpenTelemetry Demo application - a microservices-based e-commerce store selling telescopes and astronomy equipment.

### Application URL

**http://a06d7f5e0e0c949aebbaba8fb471d596-1428151517.us-west-2.elb.amazonaws.com:8080**

Browse the store, add items to cart, and attempt checkout to see the system in action.

---

## Services Reference

### Core Services

| Service | Description | Technology | Key Dependencies |
|---------|-------------|------------|------------------|
| **frontend** | Web UI serving the store | Next.js | frontend-proxy |
| **frontend-proxy** | Envoy proxy for frontend | Envoy | All backend services |
| **cart** | Shopping cart management | .NET | valkey-cart (Redis) |
| **checkout** | Order processing orchestrator | Go | payment, shipping, email, cart, currency, kafka |
| **payment** | Payment processing | Node.js | - |
| **currency** | Currency conversion | C++ | - |
| **product-catalog** | Product information | Go | - |
| **recommendation** | Product recommendations | Python | product-catalog |
| **shipping** | Shipping cost calculation | Rust | quote |
| **quote** | Shipping quotes | PHP | - |
| **email** | Order confirmation emails | Ruby | - |
| **ad** | Advertisement service | Java | - |

### Infrastructure Services

| Service | Description | Technology |
|---------|-------------|------------|
| **kafka** | Message queue | Kafka |
| **accounting** | Async order processing | Go (Kafka consumer) |
| **fraud-detection** | Fraud analysis | Kotlin (Kafka consumer) |
| **valkey-cart** | Cart data store | Valkey (Redis-compatible) |
| **postgresql** | Accounting database | PostgreSQL |
| **flagd** | Feature flag service | flagd |

### Observability Services

| Service | Description |
|---------|-------------|
| **otel-collector** | OpenTelemetry Collector - aggregates and exports telemetry |
| **jaeger** | Distributed tracing backend |
| **prometheus** | Metrics storage |
| **grafana** | Dashboards and log exploration |

---

## Service Dependency Map

```
                            ┌─────────────────┐
                            │    Frontend     │
                            │   (Next.js)     │
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │  Frontend-Proxy │
                            │    (Envoy)      │
                            └────────┬────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
        ▼                            ▼                            ▼
┌───────────────┐          ┌─────────────────┐          ┌─────────────────┐
│     Cart      │          │    Checkout     │          │ Product-Catalog │
│    (.NET)     │          │      (Go)       │          │      (Go)       │
└───────┬───────┘          └────────┬────────┘          └────────┬────────┘
        │                           │                            │
        ▼                           │                            ▼
┌───────────────┐          ┌────────┴────────────────┐  ┌─────────────────┐
│  Valkey/Redis │          │                         │  │ Recommendation  │
└───────────────┘          │                         │  │    (Python)     │
                           ▼                         ▼  └─────────────────┘
                  ┌─────────────────┐       ┌─────────────────┐
                  │    Payment      │       │    Shipping     │
                  │   (Node.js)     │       │     (Rust)      │
                  └─────────────────┘       └────────┬────────┘
                           │                         │
                           │                         ▼
                  ┌────────┴───────┐        ┌─────────────────┐
                  │                │        │     Quote       │
                  ▼                ▼        │     (PHP)       │
           ┌───────────┐    ┌───────────┐   └─────────────────┘
           │   Email   │    │   Kafka   │
           │  (Ruby)   │    └─────┬─────┘
           └───────────┘          │
                          ┌───────┴───────┐
                          │               │
                          ▼               ▼
                   ┌───────────┐   ┌───────────────┐
                   │Accounting │   │Fraud-Detection│
                   │   (Go)    │   │   (Kotlin)    │
                   └─────┬─────┘   └───────────────┘
                         │
                         ▼
                   ┌───────────┐
                   │PostgreSQL │
                   └───────────┘
```

---

## How to Use the Telemetry Systems

### Grafana (Logs + Dashboards)

**URL:** http://k8s-oteldemo-grafanap-6f80336927-c3991b69b6e4352a.elb.us-west-2.amazonaws.com/grafana

**For Logs (Loki):**
1. Click hamburger menu (☰) → **Explore**
2. Select data source: **Loki** (dropdown at top)
3. Use Label browser to filter by `service_name`
4. Example query: `{service_name="payment"} |= "error"`

**Common Log Queries:**
```
# Find all errors for a service
{service_name="payment"} |= "error"

# Filter by log level
{service_name="checkout"} | json | level="ERROR"

# Search for specific text
{service_name=~".*"} |= "Payment request failed"
```

**For Dashboards:**
1. Click hamburger menu (☰) → **Dashboards**
2. Available dashboards:
   - Demo Dashboard
   - OpenTelemetry Collector
   - SpanMetrics Dashboard

**Tips:**
- `|=` searches for text (case-sensitive)
- `|~` uses regex
- Adjust time range using picker in top right

---

### Jaeger (Traces)

**URL:** http://k8s-oteldemo-jaegerpu-ddab1a4609-a8c87825ebcf8ab1.elb.us-west-2.amazonaws.com

**Finding Traces:**
1. Select **Service** from dropdown
2. Optionally select **Operation**
3. Set **Lookback** time range (e.g., "Last Hour")
4. Click **Find Traces**

**Key Services to Search:**
- `checkoutservice` - Order flow
- `paymentservice` - Payment processing
- `cartservice` - Cart operations
- `frontend` - Web requests

**Analyzing a Trace:**
- Click any trace to expand the timeline
- **Red spans** = errors
- Look at span **tags** and **logs** for details
- Note the **duration** of each span

**Pro Tips:**
- Use **Tags** filter: `error=true` to find failures
- Click **System Architecture** tab to see service map
- Use **Compare** to diff two traces

---

### Prometheus (Metrics)

**URL:** http://k8s-oteldemo-promethe-3a69e57319-21477e674196d46e.elb.us-west-2.amazonaws.com

**Useful Queries:**

```promql
# Error rate by service (last 5 minutes)
sum(rate(calls_total{status_code="STATUS_CODE_ERROR"}[5m])) by (service_name)

# Request latency P95 by service
histogram_quantile(0.95, sum(rate(duration_milliseconds_bucket[5m])) by (le, service_name))

# Request count by service
sum(rate(calls_total[5m])) by (service_name)

# Span count by service (shows activity level)
sum(rate(spans_total[5m])) by (service_name)
```

**Tips:**
- Click **Graph** tab to visualize over time
- Use autocomplete for metric names
- Adjust evaluation time in the time picker

---

## Investigation Strategy

When an incident is announced:

### Step 1: Check Metrics (Prometheus)
```promql
sum(rate(calls_total{status_code="STATUS_CODE_ERROR"}[5m])) by (service_name)
```
→ Which service has elevated errors?

### Step 2: Find Error Traces (Jaeger)
- Search the affected service
- Filter by `error=true`
- Click through to see the full trace

### Step 3: Get Log Details (Grafana → Loki)
```
{service_name="<service>"} |= "error"
```
→ Find the actual error message and stack trace

### Step 4: Correlate
- Match timestamps across systems
- Use trace IDs to link logs ↔ traces
- Build the timeline of events

---

## Common Failure Scenarios

The following types of failures may be injected:

| Scenario | Symptoms | Where to Look |
|----------|----------|---------------|
| **Service Failure** | HTTP 500 errors, failed spans | Jaeger traces, Grafana logs |
| **High Latency** | Slow page loads, timeout errors | Prometheus latency metrics, Jaeger durations |
| **Resource Exhaustion** | OOM errors, high CPU | Prometheus container metrics |
| **Dependency Failure** | Cascading errors | Jaeger service map, trace dependencies |
| **Data Issues** | Invalid data errors | Grafana logs with validation errors |

---

## Sample Investigation Walkthrough

**Scenario:** Users report checkout is failing

1. **Check Prometheus for errors:**
   ```promql
   sum(rate(calls_total{status_code="STATUS_CODE_ERROR"}[5m])) by (service_name)
   ```
   → See `paymentservice` has high error rate

2. **Find traces in Jaeger:**
   - Service: `checkoutservice`
   - Tags: `error=true`
   → See traces failing at payment span

3. **Click into a failing trace:**
   → See error: "Payment request failed. Invalid token."

4. **Get logs in Grafana (Loki):**
   ```
   {service_name="payment"} |= "Payment request failed"
   ```
   → See full error with `app.loyalty.level=gold`

5. **Conclusion:**
   Root cause: Payment service rejecting requests with specific loyalty level

---

## Need Help?

- **Slack Channel:** [Your Slack Channel]
- **Questions about tools:** Ask in #help
- **Report bugs:** DM the organizers

Good luck and happy debugging! 🔍
