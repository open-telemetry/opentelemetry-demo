# Service Level Objectives — Critical User Paths

> **Role:** Principal Site Reliability Engineer & Observability Architect  
> **Source:** `doc/CRITICAL_USER_PATHS_ANALYSIS.md`, `doc/application-overview.md`  
> **Date:** March 2026

---

## SLO Design Principles

**Availability SLIs** are defined as the ratio of successful requests to total requests within a rolling 28-day window.  
**Latency SLIs** are defined as the proportion of requests completing within the target threshold (percentile-bucket approach), over a rolling 28-day window.  
**Error budget** = `(1 − availability_target) × total_requests`. Exhausting the error budget triggers a freeze on risky deployments.

Thresholds are justified by:
- **Service chain depth** — more downstream calls = higher aggregate latency
- **External dependency type** — database, LLM, or payment network add irreducible latency floors
- **User tolerance** — checkout users tolerate more latency than browse users; LLM users have high tolerance
- **Business impact** — higher criticality → tighter availability target, but not always tighter latency

All metric labels reference the OpenTelemetry semantic conventions used by this demo (OTLP → Prometheus via otel-collector).

---

## CUP 1 — Checkout & Payment

### Criticality: 🔴 Highest (Direct Revenue)

The checkout path is a synchronous chain of **7 services** (cart → currency → quote → payment → shipping → email) before responding. Each hop adds latency. The payment network introduces an irreducible external latency floor (~300–800 ms for card processing).

### Availability SLO

| Target | Rationale |
|---|---|
| **99.95%** per 28-day rolling window | Any outage is direct revenue loss. At 99.95%, the error budget is ~21 minutes/month — sufficient for a single hotfix deploy but not ongoing instability. |

**Error budget:** 21.6 minutes of downtime or 0.05% of requests failing per 28-day window.

### Latency SLO

| Percentile | Target | Justification |
|---|---|---|
| P50 | < 1,500 ms | Median for a 7-service chain with payment network roundtrip |
| P95 | < 3,000 ms | Covers slow payment network responses and cold-start gRPC connections |
| P99 | < 6,000 ms | Allows for occasional cart Valkey cache misses and currency conversion outliers |

The 3 s P95 target is deliberately generous compared to browse paths because the payment network (external) has a floor of ~300–800 ms, the cart and currency services add ~100–200 ms each, and the quote HTTP call adds ~200–400 ms. Tighter thresholds would create false SLO breaches driven by upstream payment network variance.

### SLI Definitions

**Availability SLI (primary — frontend BFF POST /api/checkout):**
```
sli_checkout_availability =
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/checkout",
      http_request_method="POST",
      http_response_status_code!~"5.."
  }[28d]))
  /
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/checkout",
      http_request_method="POST"
  }[28d]))
```

**Availability SLI (upstream — checkout gRPC PlaceOrder):**
```
sli_place_order_availability =
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.CheckoutService",
      rpc_method="PlaceOrder",
      rpc_grpc_status_code="0"
  }[28d]))
  /
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.CheckoutService",
      rpc_method="PlaceOrder"
  }[28d]))
```

**Latency SLI (P95 < 3,000 ms):**
```
sli_checkout_latency_p95 =
  histogram_quantile(0.95,
    sum by (le) (rate(http_server_request_duration_seconds_bucket{
        http_route="/api/checkout",
        http_request_method="POST"
    }[1h]))
  ) < 3.0
```

**Payment charge latency (P95 < 1,500 ms — isolated to payment service):**
```
sli_payment_charge_latency_p95 =
  histogram_quantile(0.95,
    sum by (le) (rate(rpc_client_duration_milliseconds_bucket{
        rpc_service="hipstershop.PaymentService",
        rpc_method="Charge"
    }[1h]))
  ) < 1500
```

---

## CUP 2 — Product Browse & Discovery

### Criticality: 🔴 High (Top-of-Funnel)

Product listing calls 2 downstream services (product-catalog + currency) in series. Product detail is a single gRPC call. Latency is dominated by the product-catalog gRPC response (~50–150 ms) and currency conversion (~20–50 ms). Images are served by nginx (near zero latency at CDN). Users are browsing; tolerance is moderate but lower than checkout.

### Availability SLO

| Target | Rationale |
|---|---|
| **99.9%** per 28-day rolling window | Browse downtime blocks all conversions but is recoverable faster than payment outages. Error budget is ~43 minutes/month. |

### Latency SLO

| Percentile | Target | Justification |
|---|---|---|
| P50 | < 300 ms | Product list (catalog gRPC + currency gRPC) should be fast; in-memory catalog |
| P95 | < 800 ms | Covers cold gRPC connections and catalog filtering overhead |
| P99 | < 1,500 ms | Accounts for recommendation service slow paths (Python startup) |

### SLI Definitions

**Availability SLI (GET /api/products):**
```
sli_browse_availability =
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/products",
      http_request_method="GET",
      http_response_status_code!~"5.."
  }[28d]))
  /
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/products",
      http_request_method="GET"
  }[28d]))
```

**Latency SLI (P95 < 800 ms):**
```
sli_browse_latency_p95 =
  histogram_quantile(0.95,
    sum by (le) (rate(http_server_request_duration_seconds_bucket{
        http_route=~"/api/products.*",
        http_request_method="GET"
    }[1h]))
  ) < 0.8
```

**Product catalog gRPC availability:**
```
sli_catalog_availability =
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.ProductCatalogService",
      rpc_grpc_status_code="0"
  }[28d]))
  /
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.ProductCatalogService"
  }[28d]))
```

---

## CUP 3 — Shopping Cart Management

### Criticality: 🔴 High (Mid-Funnel Gate)

Cart operations are simple gRPC → Valkey (Redis) calls. Latency is dominated by the Valkey roundtrip (~1–5 ms over a local network). The frontend BFF adds ~10–20 ms overhead. This path should be very fast; users expect instant feedback when adding to cart.

### Availability SLO

| Target | Rationale |
|---|---|
| **99.95%** per 28-day rolling window | Cart unavailability directly prevents checkout. Same budget as CUP 1. ~21 minutes/month error budget. |

### Latency SLO

| Percentile | Target | Justification |
|---|---|---|
| P50 | < 80 ms | Simple Valkey SET/GET; should be near-instant |
| P95 | < 300 ms | Covers Valkey connection pool exhaustion and occasional GC pauses |
| P99 | < 800 ms | Allows for Valkey restart recovery and cold connection paths |

### SLI Definitions

**Availability SLI (all /api/cart methods):**
```
sli_cart_availability =
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/cart",
      http_response_status_code!~"5.."
  }[28d]))
  /
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/cart"
  }[28d]))
```

**Latency SLI (P95 < 300 ms — add to cart is most latency-sensitive):**
```
sli_cart_latency_p95 =
  histogram_quantile(0.95,
    sum by (le) (rate(http_server_request_duration_seconds_bucket{
        http_route="/api/cart",
        http_request_method="POST"
    }[1h]))
  ) < 0.3
```

**Cart service gRPC availability:**
```
sli_cart_grpc_availability =
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.CartService",
      rpc_grpc_status_code="0"
  }[28d]))
  /
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.CartService"
  }[28d]))
```

---

## CUP 4 — Order Fulfillment & Fraud Detection

### Criticality: 🟠 High (Post-Purchase Compliance)

This path is **asynchronous** — Kafka consumers process `OrderPlacedEvent` after the checkout response is returned. Shipping and email are synchronous within `PlaceOrder`. The SLO has two dimensions: (a) synchronous fulfilment latency within checkout, and (b) async consumer processing lag.

### Availability SLO

| Component | Target | Rationale |
|---|---|---|
| **Shipping `ShipOrder`** (sync) | **99.9%** | Blocking call in PlaceOrder; failure aborts checkout |
| **Email `SendOrderConfirmation`** (sync) | **99.5%** | Failure is recoverable (retry); does not block revenue |
| **Kafka consumers — Accounting** (async) | **99.5%** | Audit ledger; failures are unacceptable but async retries compensate |
| **Kafka consumers — Fraud Detection** (async) | **99.0%** | Risk scoring; some missed events tolerable with compensating controls |

### Latency SLO

| Component | P95 Target | P99 Target | Justification |
|---|---|---|---|
| `ShipOrder` gRPC (sync, within PlaceOrder) | < 800 ms | < 2,000 ms | Internal Rust service; should be fast but address lookup may add latency |
| `SendOrderConfirmation` (sync, within PlaceOrder) | < 500 ms | < 1,500 ms | SMTP call; network-bound |
| Kafka consumer lag — Accounting | < 30 s end-to-end | < 60 s | Async; batch processing acceptable |
| Kafka consumer lag — Fraud Detection | < 60 s end-to-end | < 120 s | Risk scoring window; near-real-time acceptable |

### SLI Definitions

**Shipping service gRPC availability (ShipOrder):**
```
sli_ship_order_availability =
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.ShippingService",
      rpc_method="ShipOrder",
      rpc_grpc_status_code="0"
  }[28d]))
  /
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.ShippingService",
      rpc_method="ShipOrder"
  }[28d]))
```

**Kafka consumer lag SLI (Accounting — max lag < 30 s):**
```
sli_accounting_consumer_lag =
  kafka_consumer_group_lag{
      group="accounting-service",
      topic="orders"
  } < 1000
# Complement: processing_time = lag_messages * avg_message_processing_time < 30s
```

**Fraud detection consumer lag SLI (max lag < 60 s):**
```
sli_fraud_consumer_lag =
  kafka_consumer_group_lag{
      group="fraud-detection-service",
      topic="orders"
  } < 2000
```

---

## CUP 5 — Shipping Quote

### Criticality: 🟠 High (Checkout Blocker)

The quote service is a PHP HTTP service called **synchronously within PlaceOrder**. PHP has higher cold-start overhead than Go/Rust services. The calculation itself is simple arithmetic, but PHP process spawn time and HTTP overhead add latency. This is a synchronous blocking dependency; downtime cascades directly into CUP 1 failures.

### Availability SLO

| Target | Rationale |
|---|---|
| **99.9%** per 28-day rolling window | Failure propagates into checkout failures. However, checkout could theoretically implement a fallback quote, so slightly looser than the payment service. |

### Latency SLO

| Percentile | Target | Justification |
|---|---|---|
| P50 | < 150 ms | Simple arithmetic; PHP process should respond quickly if warm |
| P95 | < 600 ms | Covers PHP cold-start overhead (process spawn ~200–400 ms) |
| P99 | < 1,200 ms | Allows for PHP worker pool exhaustion under load |

### SLI Definitions

**Quote service HTTP availability (POST /getquote):**
```
sli_quote_availability =
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/getquote",
      http_request_method="POST",
      http_response_status_code!~"5.."
  }[28d]))
  /
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/getquote",
      http_request_method="POST"
  }[28d]))
```

**Quote latency SLI (P95 < 600 ms):**
```
sli_quote_latency_p95 =
  histogram_quantile(0.95,
    sum by (le) (rate(http_server_request_duration_seconds_bucket{
        http_route="/getquote",
        http_request_method="POST"
    }[1h]))
  ) < 0.6
```

---

## CUP 6 — Currency Selection & Price Display

### Criticality: 🔴 High (Universal Dependency)

The currency service is a C++ in-process computation using static exchange rate tables. There are no database calls; conversion is pure arithmetic. Latency should be extremely low (<10 ms for the gRPC handler). However, the service is called on **every product page load** and **inside every PlaceOrder**, making its availability critical.

### Availability SLO

| Target | Rationale |
|---|---|
| **99.95%** per 28-day rolling window | Every browse page and every checkout depends on this service. Downtime affects all users regardless of currency. ~21 minutes/month error budget. |

### Latency SLO

| Percentile | Target | Justification |
|---|---|---|
| P50 | < 20 ms | In-memory arithmetic; C++ gRPC handler should be sub-millisecond; network adds ~5–15 ms |
| P95 | < 100 ms | Covers gRPC connection establishment overhead |
| P99 | < 200 ms | Allows for GC pauses in calling services (not in C++ itself) |

### SLI Definitions

**Currency service gRPC availability:**
```
sli_currency_availability =
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.CurrencyService",
      rpc_grpc_status_code="0"
  }[28d]))
  /
  sum(rate(rpc_server_duration_count{
      rpc_service="hipstershop.CurrencyService"
  }[28d]))
```

**Convert latency SLI (P95 < 100 ms):**
```
sli_currency_convert_latency_p95 =
  histogram_quantile(0.95,
    sum by (le) (rate(rpc_server_duration_milliseconds_bucket{
        rpc_service="hipstershop.CurrencyService",
        rpc_method="Convert"
    }[1h]))
  ) < 100
```

---

## CUP 7 — AI Product Assistant

### Criticality: 🟢 Medium (Conversion Aid — Gracefully Degradable)

LLM inference is inherently slow. The service calls an OpenAI-compatible backend (local model or API). Token generation latency scales with response length. Users explicitly trigger this feature and understand it is "AI-powered" — tolerance for latency is significantly higher than for browse or cart. The service is gracefully degradable (UI can show a timeout message without blocking purchase).

### Availability SLO

| Target | Rationale |
|---|---|
| **99.0%** per 28-day rolling window | Non-blocking; users can proceed without AI assistance. Lower target reflects acceptable graceful degradation. ~7.2 hours/month error budget. |

### Latency SLO

| Percentile | Target | Justification |
|---|---|---|
| P50 | < 5,000 ms | LLM token generation for a ~200-token response at typical inference speed |
| P95 | < 10,000 ms | Covers model loading overhead and concurrent request queuing |
| P99 | < 20,000 ms | Timeout threshold; requests exceeding this should return a graceful error |

### SLI Definitions

**LLM service availability (POST /v1/chat/completions):**
```
sli_llm_availability =
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/v1/chat/completions",
      http_request_method="POST",
      http_response_status_code!~"5.."
  }[28d]))
  /
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/v1/chat/completions",
      http_request_method="POST"
  }[28d]))
```

**AI assistant BFF availability:**
```
sli_ai_assistant_availability =
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/product-ask-ai-assistant/[productId]",
      http_request_method="POST",
      http_response_status_code!~"5.."
  }[28d]))
  /
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/product-ask-ai-assistant/[productId]",
      http_request_method="POST"
  }[28d]))
```

**LLM latency SLI (P95 < 10 s):**
```
sli_llm_latency_p95 =
  histogram_quantile(0.95,
    sum by (le) (rate(http_server_request_duration_seconds_bucket{
        http_route="/v1/chat/completions"
    }[1h]))
  ) < 10.0
```

---

## CUP 8 — Product Reviews

### Criticality: 🟢 Medium-Low (Trust Signal — Non-Blocking)

Review reads are PostgreSQL SELECT queries. Latency is dominated by the DB query (~5–50 ms) and Python gRPC overhead (~20–50 ms). Review writes involve an INSERT. Neither operation blocks purchase flow; downtime reduces purchase confidence but does not prevent transactions.

### Availability SLO

| Target | Rationale |
|---|---|
| **99.5%** per 28-day rolling window | Non-blocking; front end can gracefully hide the reviews section on error. ~3.6 hours/month error budget. |

### Latency SLO

| Percentile | Target | Justification |
|---|---|---|
| P50 | < 200 ms | Single PostgreSQL SELECT with index on `product_id` |
| P95 | < 500 ms | Covers PostgreSQL connection pool contention under load |
| P99 | < 1,000 ms | Allows for PostgreSQL VACUUM or index rebuild overhead |

### SLI Definitions

**Reviews BFF availability (GET /api/product-reviews/[productId]):**
```
sli_reviews_availability =
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/product-reviews/[productId]",
      http_request_method="GET",
      http_response_status_code!~"5.."
  }[28d]))
  /
  sum(rate(http_server_request_duration_seconds_count{
      http_route="/api/product-reviews/[productId]",
      http_request_method="GET"
  }[28d]))
```

**Product reviews gRPC service availability:**
```
sli_reviews_grpc_availability =
  sum(rate(rpc_server_duration_count{
      rpc_service="oteldemo.ProductReviewService",
      rpc_grpc_status_code="0"
  }[28d]))
  /
  sum(rate(rpc_server_duration_count{
      rpc_service="oteldemo.ProductReviewService"
  }[28d]))
```

**Reviews latency SLI (P95 < 500 ms):**
```
sli_reviews_latency_p95 =
  histogram_quantile(0.95,
    sum by (le) (rate(http_server_request_duration_seconds_bucket{
        http_route="/api/product-reviews/[productId]",
        http_request_method="GET"
    }[1h]))
  ) < 0.5
```

---

## Consolidated SLO Reference Table

| CUP | Availability Target | P95 Latency | P99 Latency | Error Budget (28d) |
|---|---|---|---|---|
| 1 — Checkout & Payment | **99.95%** | < 3,000 ms | < 6,000 ms | 21.6 min |
| 2 — Product Browse & Discovery | **99.9%** | < 800 ms | < 1,500 ms | 43.2 min |
| 3 — Shopping Cart Management | **99.95%** | < 300 ms | < 800 ms | 21.6 min |
| 4 — Order Fulfillment (ShipOrder) | **99.9%** | < 800 ms | < 2,000 ms | 43.2 min |
| 4 — Order Fulfillment (Async consumers) | **99.5%** | < 30 s lag | < 60 s lag | 3.6 hr |
| 5 — Shipping Quote | **99.9%** | < 600 ms | < 1,200 ms | 43.2 min |
| 6 — Currency Selection | **99.95%** | < 100 ms | < 200 ms | 21.6 min |
| 7 — AI Product Assistant | **99.0%** | < 10,000 ms | < 20,000 ms | 7.2 hr |
| 8 — Product Reviews | **99.5%** | < 500 ms | < 1,000 ms | 3.6 hr |

---

## Alerting Thresholds (Burn Rate)

Using the **multi-window burn rate** approach (Google SRE Workbook Chapter 5):

| Severity | Burn Rate | Detection Window | Action |
|---|---|---|---|
| 🚨 Page (P1) | > 14.4× | 1 h (short) + 5 min (fast) | Immediate on-call response |
| ⚠️ Ticket (P2) | > 6× | 6 h (short) + 30 min (fast) | Response within 4 hours |
| 📋 Warning (P3) | > 1× | 3 days | Review in next sprint |

**Example alert for CUP 1 (Checkout P1):**
```yaml
# Fires if checkout burns through 2% of monthly error budget in 1 hour
# (14.4x burn rate means the budget would exhaust in 2 days at this rate)
- alert: CheckoutErrorBudgetBurnRateCritical
  expr: |
    (
      sum(rate(http_server_request_duration_seconds_count{
          http_route="/api/checkout",
          http_response_status_code=~"5.."
      }[1h]))
      /
      sum(rate(http_server_request_duration_seconds_count{
          http_route="/api/checkout"
      }[1h]))
    ) > (14.4 * 0.0005)
  for: 2m
  labels:
    severity: critical
    cup: checkout_payment
  annotations:
    summary: "Checkout error budget burning at >14.4x rate"
    runbook: "https://runbooks/checkout-payment-slo"