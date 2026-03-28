# OpenTelemetry SDK Instrumentation Plan — Critical User Paths
## Astronomy Shop (opentelemetry-demo)

> **Authors:** Observability & SRE Architecture Team  
> **Date:** March 2026  
> **Status:** Draft — For Engineering Implementation, SRE Review & Architecture Approval  
> **Sources:** `doc/CRITICAL_USER_PATHS_ANALYSIS.md`, `doc/CRITICAL_USER_PATHS_SLO.md`, `doc/application-overview.md`, codebase inspection

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Critical User Path Overview Table](#2-critical-user-path-overview-table)
3. [SLO → Telemetry Mapping](#3-slo--telemetry-mapping)
4. [Per-CUP SDK Instrumentation Plans](#4-per-cup-sdk-instrumentation-plans)
   - [CUP 1 — Checkout & Payment](#cup-1--checkout--payment)
   - [CUP 2 — Product Browse & Discovery](#cup-2--product-browse--discovery)
   - [CUP 3 — Shopping Cart Management](#cup-3--shopping-cart-management)
   - [CUP 4 — Order Fulfillment & Fraud Detection](#cup-4--order-fulfillment--fraud-detection)
   - [CUP 5 — Shipping Quote](#cup-5--shipping-quote)
   - [CUP 6 — Currency Selection & Price Display](#cup-6--currency-selection--price-display)
   - [CUP 7 — AI Product Assistant](#cup-7--ai-product-assistant)
   - [CUP 8 — Product Reviews](#cup-8--product-reviews)
5. [OTel SDK Standards](#5-otel-sdk-standards)
6. [Rollout & Migration Plan](#6-rollout--migration-plan)
7. [Sampling Strategy](#7-sampling-strategy)
8. [Risks & Guardrails](#8-risks--guardrails)
9. [Appendix: Code Examples](#9-appendix-code-examples)

---

## 1. Executive Summary

This document is the **single authoritative instrumentation specification** for adding OpenTelemetry SDK observability to all services participating in the eight Critical User Paths (CUPs) of the Astronomy Shop platform.

### Why This Plan Exists

The Astronomy Shop is a **polyglot, 17-service microservices system** spanning Go, TypeScript, C#, C++, Node.js, Python, Ruby, PHP, Rust, Java, and Kotlin. Several services (checkout, payment, frontend) already carry foundational OTel instrumentation. The goal of this plan is to:

1. **Fill instrumentation gaps** — identify services with missing or incomplete spans, metrics, or logs.
2. **Make SLOs measurable** — ensure each SLO defined in `CRITICAL_USER_PATHS_SLO.md` has corresponding telemetry signals that can drive the Prometheus-based SLI expressions.
3. **Align telemetry to business paths** — instrument at the path level, not just at the service level, ensuring that a broken checkout trace is self-evident without querying five separate dashboards.
4. **Protect production** — define cardinality limits, PII guardrails, sampling policies, and incremental rollout gates.

### Instrumentation Maturity Baseline (as of March 2026)

| Service | Language | Traces | Metrics | Logs | Gaps |
|---|---|---|---|---|---|
| checkout | Go | ✅ Full | ✅ Runtime | ✅ OTel slog | Business metrics missing |
| payment | Node.js | ✅ Manual spans | ✅ Counter | ✅ Logger | Histogram for charge duration |
| frontend | TypeScript | ⚠️ Middleware only | ❌ None | ⚠️ Partial | Custom business spans; metric counters |
| cart | C# | ⚠️ gRPC auto | ❌ None | ❌ None | gRPC server handler; metrics; logging |
| currency | C++ | ❌ None | ❌ None | ❌ None | Full SDK setup required |
| product-catalog | Go | ⚠️ Partial | ❌ None | ⚠️ Partial | Cache hit/miss metrics; gRPC auto |
| quote | PHP | ❌ None | ❌ None | ❌ None | Full SDK setup required |
| shipping | Rust | ❌ None | ❌ None | ❌ None | Full SDK setup required |
| email | Ruby | ❌ None | ❌ None | ❌ None | Full SDK setup required |
| accounting | C# | ⚠️ Kafka consumer partial | ❌ None | ❌ None | Consumer lag metrics |
| fraud-detection | Kotlin | ⚠️ Kafka consumer partial | ❌ None | ❌ None | Consumer lag metrics |
| recommendation | Python | ⚠️ gRPC auto | ❌ None | ❌ None | Business logic spans |
| ad | Java | ⚠️ Spring Boot auto | ⚠️ JVM metrics | ⚠️ Logback | Ad serving counters |
| llm | Python | ⚠️ HTTP auto | ❌ None | ❌ None | Token metrics; latency histogram |
| product-reviews | Python | ❌ None | ❌ None | ❌ None | Full SDK setup required |

### Key Decisions

- **Always-on tracing** for CUP 1 (Checkout) and CUP 3 (Cart) — zero sampling loss on revenue paths.
- **Tail sampling** for CUP 2 (Browse) — high-volume; retain all errors, sample happy-path at 10%.
- **Shared SDK bootstrap library** pattern per language group (Go, .NET, Python, JVM) to avoid 17 independent setups.
- **No PII in spans** — user email, card numbers, PAN, CVV must never appear as span attributes or log fields.
- **Semantic convention alignment** — all metrics and attributes use OTel semconv v1.24+ to enable SLI expressions without label transforms.

---

## 2. Critical User Path Overview Table

| Priority | CUP Name | Business Impact | SLO Availability | SLO P95 Latency | Services Instrumented | Entry Point |
|---|---|---|---|---|---|---|
| **P1** | Checkout & Payment | 🔴 Direct revenue loss per minute | 99.95% | < 3,000 ms | frontend, checkout, cart, currency, quote, payment, shipping, email, kafka | `POST /api/checkout` |
| **P2** | Product Browse & Discovery | 🔴 Blocks entire purchase funnel | 99.9% | < 800 ms | frontend, product-catalog, recommendation, ad, currency | `GET /api/products` |
| **P3** | Shopping Cart Management | 🔴 Mid-funnel gate to checkout | 99.95% | < 300 ms | frontend, cart | `POST/GET/DELETE /api/cart` |
| **P4** | Order Fulfillment & Fraud | 🟠 Post-purchase trust & compliance | 99.9% (sync) / 99.5% (async) | < 800 ms (ShipOrder) / < 30 s lag | checkout, shipping, email, kafka, accounting, fraud-detection | Kafka `orders` topic |
| **P5** | Shipping Quote | 🟠 Checkout completion blocker | 99.9% | < 600 ms | frontend, quote, shipping | `POST /getquote` |
| **P6** | Currency Selection | 🔴 Universal price dependency | 99.95% | < 100 ms | frontend, currency | `GET /api/currency` |
| **P7** | AI Product Assistant | 🟢 Conversion aid; gracefully degradable | 99.0% | < 10,000 ms | frontend, llm, product-catalog | `POST /api/product-ask-ai-assistant/[productId]` |
| **P8** | Product Reviews | 🟢 Trust signal; non-blocking | 99.5% | < 500 ms | frontend, product-reviews, postgresql | `GET /api/product-reviews/[productId]` |

### Service × CUP Participation Matrix

| Service | Lang | CUP1 | CUP2 | CUP3 | CUP4 | CUP5 | CUP6 | CUP7 | CUP8 |
|---|---|---|---|---|---|---|---|---|---|
| frontend | TS | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| frontend-proxy | Envoy | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| checkout | Go | ✅ | — | — | ✅ | ✅ | — | — | — |
| payment | Node.js | ✅ | — | — | — | — | — | — | — |
| cart | C# | ✅ | — | ✅ | — | — | — | — | — |
| currency | C++ | ✅ | ✅ | — | — | — | ✅ | — | — |
| quote | PHP | ✅ | — | — | — | ✅ | — | — | — |
| shipping | Rust | ✅ | — | — | ✅ | ✅ | — | — | — |
| email | Ruby | ✅ | — | — | ✅ | — | — | — | — |
| kafka | Kafka | ✅ | — | — | ✅ | — | — | — | — |
| accounting | C# | — | — | — | ✅ | — | — | — | — |
| fraud-detection | Kotlin | — | — | — | ✅ | — | — | — | — |
| product-catalog | Go | — | ✅ | — | — | — | — | ✅ | — |
| recommendation | Python | — | ✅ | — | — | — | — | — | — |
| ad | Java | — | ✅ | — | — | — | — | — | — |
| llm | Python | — | — | — | — | — | — | ✅ | — |
| product-reviews | Python | — | — | — | — | — | — | — | ✅ |
| postgresql | PostgreSQL | — | — | — | — | — | — | — | ✅ |

---

## 3. SLO → Telemetry Mapping

This table maps each SLO to the specific telemetry signals (spans, metrics, logs) that must be present to evaluate it. Gaps in this table represent instrumentation gaps that must be closed.

### 3.1 Availability SLOs

| CUP | SLO Target | Required Metric | Source Service | Span / Metric Name | Status |
|---|---|---|---|---|---|
| CUP 1 | 99.95% | `http_server_request_duration_seconds_count` | frontend | `http.route="/api/checkout"` | ⚠️ Needs HTTP status label |
| CUP 1 | 99.95% | `rpc_server_duration_count` | checkout | `rpc.service="hipstershop.CheckoutService"` | ✅ Exists via otelgrpc |
| CUP 2 | 99.9% | `http_server_request_duration_seconds_count` | frontend | `http.route="/api/products"` | ⚠️ Needs route label |
| CUP 2 | 99.9% | `rpc_server_duration_count` | product-catalog | `rpc.service="hipstershop.ProductCatalogService"` | ❌ Missing |
| CUP 3 | 99.95% | `http_server_request_duration_seconds_count` | frontend | `http.route="/api/cart"` | ⚠️ Needs status label |
| CUP 3 | 99.95% | `rpc_server_duration_count` | cart | `rpc.service="hipstershop.CartService"` | ❌ Missing |
| CUP 4 | 99.9% (sync) | `rpc_server_duration_count` | shipping | `rpc.method="ShipOrder"` | ❌ Missing |
| CUP 4 | 99.5% (async) | `kafka_consumer_group_lag` | kafka/accounting | `group="accounting-service"` | ❌ Missing |
| CUP 4 | 99.0% (async) | `kafka_consumer_group_lag` | kafka/fraud-detection | `group="fraud-detection-service"` | ❌ Missing |
| CUP 5 | 99.9% | `http_server_request_duration_seconds_count` | quote | `http.route="/getquote"` | ❌ Missing |
| CUP 6 | 99.95% | `rpc_server_duration_count` | currency | `rpc.service="hipstershop.CurrencyService"` | ❌ Missing |
| CUP 7 | 99.0% | `http_server_request_duration_seconds_count` | llm | `http.route="/v1/chat/completions"` | ❌ Missing |
| CUP 8 | 99.5% | `http_server_request_duration_seconds_count` | frontend | `http.route="/api/product-reviews/[productId]"` | ❌ Missing |
| CUP 8 | 99.5% | `rpc_server_duration_count` | product-reviews | `rpc.service="oteldemo.ProductReviewService"` | ❌ Missing |

### 3.2 Latency SLOs

| CUP | P95 Target | Required Metric | Source | Histogram Bucket Configuration |
|---|---|---|---|---|
| CUP 1 | 3,000 ms | `http_server_request_duration_seconds_bucket` | frontend | Buckets: 0.1, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 6.0, 10.0 |
| CUP 1 (payment) | 1,500 ms | `rpc_client_duration_milliseconds_bucket` | checkout | Buckets: 100, 300, 500, 800, 1000, 1500, 3000 |
| CUP 2 | 800 ms | `http_server_request_duration_seconds_bucket` | frontend | Buckets: 0.05, 0.1, 0.2, 0.4, 0.8, 1.5, 3.0 |
| CUP 3 | 300 ms | `http_server_request_duration_seconds_bucket` | frontend | Buckets: 0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8 |
| CUP 4 (ShipOrder) | 800 ms | `rpc_server_duration_milliseconds_bucket` | shipping | Buckets: 100, 300, 500, 800, 1200, 2000 |
| CUP 5 | 600 ms | `http_server_request_duration_seconds_bucket` | quote | Buckets: 0.05, 0.1, 0.2, 0.4, 0.6, 1.0, 1.2 |
| CUP 6 | 100 ms | `rpc_server_duration_milliseconds_bucket` | currency | Buckets: 1, 5, 10, 20, 50, 100, 200 |
| CUP 7 | 10,000 ms | `http_server_request_duration_seconds_bucket` | llm | Buckets: 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0 |
| CUP 8 | 500 ms | `http_server_request_duration_seconds_bucket` | frontend | Buckets: 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0 |

### 3.3 Business Metrics SLOs

| CUP | Business Signal | Metric Name | Type | Labels |
|---|---|---|---|---|
| CUP 1 | Order completion rate | `app.orders.placed.total` | Counter | `currency`, `status` |
| CUP 1 | Payment success rate | `app.payment.transactions.total` | Counter | `currency`, `card_type`, `status` |
| CUP 1 | Revenue value per order | `app.order.amount` | Histogram | `currency` |
| CUP 2 | Product page views | `app.product.views.total` | Counter | `product_id`, `category` |
| CUP 3 | Cart add rate | `app.cart.items.added.total` | Counter | — |
| CUP 4 | Kafka consumer lag (seconds) | `app.kafka.consumer.lag.seconds` | Gauge | `group`, `topic` |
| CUP 7 | LLM request success rate | `app.llm.requests.total` | Counter | `model`, `status` |
| CUP 7 | LLM token count | `app.llm.tokens.used.total` | Counter | `model`, `type` (prompt/completion) |

---

## 4. Per-CUP SDK Instrumentation Plans

---

### CUP 1 — Checkout & Payment

**Priority:** P1 | **Availability SLO:** 99.95% | **P95 Latency:** < 3,000 ms

#### 4.1.1 Tracing Plan

**Root span:** `POST /api/checkout` — created by frontend BFF via HTTP auto-instrumentation.

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `POST /api/checkout` | frontend | Server | — (root) | `http.route`, `http.method`, `http.response_status_code`, `app.user.currency` |
| `hipstershop.CheckoutService/PlaceOrder` | checkout | Server | frontend root | `app.user.id`, `app.user.currency`, `app.order.id`, `app.order.amount`, `app.order.items.count` |
| `prepareOrderItemsAndShippingQuoteFromCart` | checkout | Internal | PlaceOrder | `app.cart.items.count`, `app.shipping.amount` |
| `hipstershop.CartService/GetCart` | cart | Server | checkout | `app.user.id` |
| `db.valkey.get` | cart | Client | GetCart | `db.system="redis"`, `db.operation="GET"`, `db.redis.key="cart:{userId}"` (no PII in key) |
| `hipstershop.CurrencyService/Convert` | currency | Server | checkout | `app.currency.from`, `app.currency.to` |
| `POST /get-quote` | checkout→quote | Client | checkout | `http.url` (host only, no query params) |
| `POST /getquote` | quote | Server | checkout | `app.quote.items_count`, `app.quote.cost_usd` |
| `hipstershop.PaymentService/Charge` | payment | Server | checkout | `app.payment.card_type`, `app.payment.card_valid`, `app.payment.charged`, `app.loyalty.level` |
| `POST /ship-order` | checkout→shipping | Client | checkout | `http.url` (host only) |
| `POST /ship-order` | shipping | Server | checkout | `app.shipping.tracking.id` |
| `POST /send_order_confirmation` | checkout→email | Client | checkout | `http.url` (host only) |
| `POST /send_order_confirmation` | email | Server | checkout | `app.email.status` (no email address) |
| `orders publish` | checkout | Producer | checkout | `messaging.system="kafka"`, `messaging.destination.name="orders"`, `messaging.operation="publish"` |

**Span events (milestones within PlaceOrder):**
- `prepared` — after cart + shipping quote ready
- `charged` — after payment success (with `app.payment.transaction.id`)
- `shipped` — after shipping confirmed (with `app.shipping.tracking.id`)

**Fan-out handling:**
The Kafka publish to the `orders` topic propagates the W3C TraceContext via Kafka message headers (already implemented in `checkout/kafka/producer.go`). Consumers must extract this context to create a linked span, maintaining trace continuity across the async boundary.

**⚠️ PII Rules for CUP 1:**
- **NEVER** add `creditCardNumber`, `creditCardCvv`, `email`, or `userAddress` as span attributes.
- Use `app.user.id` (non-PII session ID) rather than email.
- `lastFourDigits` of card number is acceptable if operationally required; document explicitly.
- Payment transaction ID (`app.payment.transaction.id`) is safe to record.

#### 4.1.2 Metrics Plan

| Metric Name | Type | Service | Labels | SLO Purpose |
|---|---|---|---|---|
| `http_server_request_duration_seconds` | Histogram | frontend | `http.route`, `http.method`, `http.response_status_code` | CUP1 availability + latency SLI |
| `rpc_server_duration` | Histogram | checkout, cart | `rpc.service`, `rpc.method`, `rpc.grpc_status_code` | gRPC SLI for PlaceOrder, GetCart |
| `rpc_client_duration` | Histogram | checkout | `rpc.service`, `rpc.method` | Downstream payment, currency latency |
| `app.payment.transactions` | Counter | payment | `app.payment.currency`, `app.payment.card_type`, `app.payment.status` | Payment success rate |
| `app.orders.placed` | Counter | checkout | `app.user.currency`, `app.order.status` | Order completion rate |
| `app.order.amount` | Histogram | checkout | `app.user.currency` | Revenue per order |
| `app.checkout.duration` | Histogram | checkout | `app.user.currency` | End-to-end checkout time |

**Histogram bucket alignment for CUP 1 latency SLO (P95 < 3,000 ms):**
```
buckets: [0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 6.0, 10.0]
```

#### 4.1.3 Error & Failure Semantics

| Condition | Span Status | Error Count | Notes |
|---|---|---|---|
| gRPC status != OK from any downstream | `ERROR` | ✅ Count | Record gRPC status code on span |
| HTTP 5xx from quote or email service | `ERROR` | ✅ Count | Record response code |
| Payment card declined (business error) | `ERROR` | ✅ Count | Attribute: `app.payment.decline_reason` |
| Payment card invalid format | `ERROR` | ✅ Count | NOT a service error — user input error |
| HTTP 4xx user validation errors | `UNSET` | ❌ Exclude from SLI | User errors do not burn SLO budget |
| Cart empty at checkout | `ERROR` | ✅ Count | Business error — blocks order |
| Kafka publish failure | `ERROR` | ✅ Count | Does not block checkout response; alert separately |
| Email send failure (non-blocking) | `WARN` log | ❌ Exclude from SLI | Checkout still succeeds; logged separately |

---

### CUP 2 — Product Browse & Discovery

**Priority:** P2 | **Availability SLO:** 99.9% | **P95 Latency:** < 800 ms

#### 4.2.1 Tracing Plan

**Root span:** `GET /api/products` — created by frontend BFF auto-instrumentation.

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `GET /api/products` | frontend | Server | — (root) | `http.route`, `http.response_status_code` |
| `hipstershop.ProductCatalogService/ListProducts` | product-catalog | Server | frontend | `app.products.count` |
| `hipstershop.CurrencyService/GetSupportedCurrencies` | currency | Server | frontend | — |
| `GET /api/products/{productId}` | frontend | Server | — (root) | `http.route`, `app.product.id` |
| `hipstershop.ProductCatalogService/GetProduct` | product-catalog | Server | frontend | `app.product.id`, `app.product.category` |
| `GET /api/recommendations` | frontend | Server | — (root) | `http.route` |
| `hipstershop.RecommendationService/ListRecommendations` | recommendation | Server | frontend | `app.recommendation.input_count`, `app.recommendation.result_count` |
| `GET /api/data` | frontend | Server | — (root) | `http.route` |
| `hipstershop.AdService/GetAds` | ad | Server | frontend | `app.ad.context_keys`, `app.ad.count` |

**Fan-out note:** The product listing page calls product-catalog and currency service. These calls can be parallelised; the frontend should use W3C TraceContext headers on both gRPC calls so they appear as child spans of the same root.

#### 4.2.2 Metrics Plan

| Metric Name | Type | Service | Labels | SLO Purpose |
|---|---|---|---|---|
| `http_server_request_duration_seconds` | Histogram | frontend | `http.route`, `http.method`, `http.response_status_code` | CUP2 availability + latency SLI |
| `rpc_server_duration` | Histogram | product-catalog | `rpc.service`, `rpc.method`, `rpc.grpc_status_code` | Catalog service SLI |
| `app.product.catalog.size` | Gauge | product-catalog | — | Product count monitoring |
| `app.product.views` | Counter | frontend | `app.product.category` | Browse engagement |
| `app.recommendations.served` | Counter | recommendation | `app.recommendation.algorithm` | Recommendation quality |
| `app.ads.served` | Counter | ad | `app.ad.context_key` | Ad serving rate |

**Histogram bucket alignment for CUP 2 latency SLO (P95 < 800 ms):**
```
buckets: [0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.5, 3.0]
```

#### 4.2.3 Error & Failure Semantics

| Condition | Span Status | Error Count | Notes |
|---|---|---|---|
| product-catalog gRPC error | `ERROR` | ✅ Count | Core browse failure — burns SLO budget |
| currency service gRPC error | `ERROR` | ✅ Count | Prices unavailable — burns SLO budget |
| recommendation service error | `WARN` | ❌ Exclude from SLI | Degradable; page still usable |
| ad service error | `WARN` | ❌ Exclude from SLI | Non-blocking; monetisation only |
| Product not found (404) | `UNSET` | ❌ Exclude | User navigation error |

---

### CUP 3 — Shopping Cart Management

**Priority:** P3 | **Availability SLO:** 99.95% | **P95 Latency:** < 300 ms

#### 4.3.1 Tracing Plan

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `POST /api/cart` | frontend | Server | — (root) | `http.route`, `http.method`, `http.response_status_code` |
| `GET /api/cart` | frontend | Server | — (root) | `http.route` |
| `DELETE /api/cart` | frontend | Server | — (root) | `http.route` |
| `hipstershop.CartService/AddItem` | cart | Server | frontend | `app.cart.item.product_id`, `app.cart.item.quantity` |
| `hipstershop.CartService/GetCart` | cart | Server | frontend | `app.cart.items.count`, `app.user.id` |
| `hipstershop.CartService/EmptyCart` | cart | Server | frontend/checkout | `app.user.id` |
| `db.valkey.set` | cart | Client | AddItem | `db.system="redis"`, `db.operation="SET"`, `net.peer.name` |
| `db.valkey.get` | cart | Client | GetCart | `db.system="redis"`, `db.operation="GET"` |
| `db.valkey.del` | cart | Client | EmptyCart | `db.system="redis"`, `db.operation="DEL"` |

**Valkey/Redis span attributes:** Use `db.system="redis"`, `db.operation`, `net.peer.name`, `net.peer.port`. **Do NOT include** `db.statement` or the actual key value containing user IDs in most environments (configurable per environment).

#### 4.3.2 Metrics Plan

| Metric Name | Type | Service | Labels | SLO Purpose |
|---|---|---|---|---|
| `http_server_request_duration_seconds` | Histogram | frontend | `http.route`, `http.method`, `http.response_status_code` | Cart availability + latency SLI |
| `rpc_server_duration` | Histogram | cart | `rpc.service`, `rpc.method`, `rpc.grpc_status_code` | Cart gRPC SLI |
| `db.client.operation.duration` | Histogram | cart | `db.system`, `db.operation` | Valkey latency monitoring |
| `app.cart.items.added` | Counter | cart | — | Cart activity rate |
| `app.cart.items.count` | Histogram | cart | — | Cart size distribution |
| `app.cart.errors` | Counter | cart | `app.cart.error_type` | Valkey error rate |

**Histogram bucket alignment for CUP 3 latency SLO (P95 < 300 ms):**
```
buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8]
```

#### 4.3.3 Error & Failure Semantics

| Condition | Span Status | Error Count | Notes |
|---|---|---|---|
| Valkey connection failure | `ERROR` | ✅ Count | High severity — burns cart SLO budget |
| Valkey timeout | `ERROR` | ✅ Count | High severity |
| Cart service gRPC UNAVAILABLE | `ERROR` | ✅ Count | Service down |
| Item not found in cart | `UNSET` | ❌ Exclude | User state issue |
| Feature flag induced failure | `ERROR` | ✅ Count but label `synthetic=true` | Must distinguish from real failures |

---

### CUP 4 — Order Fulfillment & Fraud Detection

**Priority:** P4 | **Availability SLO:** 99.9% (sync) / 99.5% (async) | **P95 Latency:** < 800 ms (ShipOrder)

#### 4.4.1 Tracing Plan

This path has two distinct tracing modes: **synchronous** (within PlaceOrder) and **asynchronous** (Kafka consumers).

**Synchronous spans (within PlaceOrder in checkout):**

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `POST /ship-order` | checkout | Client | PlaceOrder | `http.url` (host only), `net.peer.name` |
| `shipOrder` handler | shipping | Server | checkout | `app.shipping.address.country`, `app.shipping.items.count`, `app.shipping.tracking.id` |
| `POST /send_order_confirmation` | checkout | Client | PlaceOrder | `http.url` (host only) |
| `sendOrderConfirmation` handler | email | Server | checkout | `app.email.status`, `app.email.template` (no email address in attributes) |

**Asynchronous spans (Kafka consumers — must use linked spans, not child spans):**

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `orders publish` | checkout | Producer | PlaceOrder | `messaging.system`, `messaging.destination.name`, `messaging.operation` |
| `orders process` | accounting | Consumer | *Link* to producer span | `messaging.consumer.group.name`, `app.order.id`, `app.accounting.ledger.entry_id` |
| `orders process` | fraud-detection | Consumer | *Link* to producer span | `messaging.consumer.group.name`, `app.fraud.score`, `app.fraud.decision` |

**Context propagation for Kafka:**
- Producer: Inject W3C `traceparent` and `tracestate` into Kafka message headers (already implemented in checkout).
- Consumers: Extract context from Kafka message headers and create a **new root span with a link** to the producer span. Do NOT create child spans — this would incorrectly merge async and sync latency.

```
checkout PlaceOrder [sync span]
   └─ orders publish [producer span]  ← traceparent injected into Kafka header

accounting [separate trace]
   └─ orders process [consumer span] ← Link → checkout's producer span
```

#### 4.4.2 Metrics Plan

| Metric Name | Type | Service | Labels | SLO Purpose |
|---|---|---|---|---|
| `rpc_server_duration` | Histogram | shipping | `rpc.service="hipstershop.ShippingService"`, `rpc.method`, `rpc.grpc_status_code` | ShipOrder SLI |
| `app.kafka.consumer.lag` | Gauge | accounting, fraud-detection | `messaging.consumer.group.name`, `messaging.destination.name` | Consumer lag SLI |
| `app.kafka.consumer.processing.duration` | Histogram | accounting, fraud-detection | `messaging.consumer.group.name` | Processing time SLI |
| `app.fulfillment.orders.processed` | Counter | accounting | `app.order.status` | Fulfillment rate |
| `app.fraud.assessments` | Counter | fraud-detection | `app.fraud.decision` (allow/flag/block) | Fraud detection rate |
| `app.email.sent` | Counter | email | `app.email.status` (sent/failed) | Email delivery rate |

#### 4.4.3 Error & Failure Semantics

| Condition | Span Status | Error Count | Notes |
|---|---|---|---|
| ShipOrder gRPC error (sync) | `ERROR` | ✅ Count | Blocks checkout — critical |
| Email send failure | `ERROR` | ✅ Count (but separate SLO budget) | Non-blocking to revenue |
| Kafka publish failure | `ERROR` | ✅ Count | Audit/fraud miss — compliance risk |
| Accounting consumer exception | `ERROR` | ✅ Count | Financial audit risk |
| Fraud detection consumer exception | `ERROR` | ✅ Count | Risk control gap |
| Consumer lag exceeds 30 s (accounting) | Metric alert | N/A | Not a span status — use metric alert |
| Consumer lag exceeds 60 s (fraud) | Metric alert | N/A | Not a span status — use metric alert |

---

### CUP 5 — Shipping Quote

**Priority:** P5 | **Availability SLO:** 99.9% | **P95 Latency:** < 600 ms

#### 4.5.1 Tracing Plan

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `GET /api/shipping` | frontend | Server | — (root) | `http.route`, `http.response_status_code` |
| `POST /getquote` | quote | Server | frontend or checkout | `app.quote.items_count`, `app.quote.cost_usd`, `app.quote.address.country` |
| `quote.calculate` | quote | Internal | POST /getquote | `app.quote.algorithm`, `app.quote.duration_ms` |
| `hipstershop.ShippingService/GetQuote` | shipping | Server | checkout (during PlaceOrder) | `app.shipping.items_count`, `app.quote.cost_usd` |

**PHP-specific tracing note:** PHP does not maintain in-process state between requests. Each request initialises the SDK fresh. Use the `opentelemetry-auto-http-client` and `opentelemetry-auto-laravel` (or slim) packages. The W3C TraceContext header from the calling service (checkout or frontend) must be extracted on each request using the `TextMapPropagator`.

#### 4.5.2 Metrics Plan

| Metric Name | Type | Service | Labels | SLO Purpose |
|---|---|---|---|---|
| `http_server_request_duration_seconds` | Histogram | quote | `http.route="/getquote"`, `http.response_status_code` | Quote availability + latency SLI |
| `app.quote.cost` | Histogram | quote | `app.quote.address.country` | Quote value distribution |
| `app.quote.requests` | Counter | quote | `app.quote.status` | Quote request rate |

#### 4.5.3 Error & Failure Semantics

| Condition | Span Status | Error Count | Notes |
|---|---|---|---|
| PHP fatal error or 500 | `ERROR` | ✅ Count | Direct checkout blocker |
| Quote returns zero cost (business error) | `ERROR` | ✅ Count | Prevents valid checkout |
| Invalid address (400) | `UNSET` | ❌ Exclude | User input error |
| PHP worker pool exhaustion (503) | `ERROR` | ✅ Count | Infrastructure issue |

---

### CUP 6 — Currency Selection & Price Display

**Priority:** P6 | **Availability SLO:** 99.95% | **P95 Latency:** < 100 ms

#### 4.6.1 Tracing Plan

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `GET /api/currency` | frontend | Server | — (root) | `http.route`, `http.response_status_code` |
| `hipstershop.CurrencyService/GetSupportedCurrencies` | currency | Server | frontend | `app.currency.codes_count` |
| `hipstershop.CurrencyService/Convert` | currency | Server | frontend/checkout | `app.currency.from`, `app.currency.to`, `app.currency.rate` |

**C++ SDK setup note:** The currency service is C++ 17. Use `opentelemetry-cpp` SDK with the OTLP gRPC exporter. The gRPC server interceptor provides automatic span creation for incoming RPC calls; no manual span creation needed for the currency service RPC handlers unless adding business attributes.

#### 4.6.2 Metrics Plan

| Metric Name | Type | Service | Labels | SLO Purpose |
|---|---|---|---|---|
| `rpc_server_duration` | Histogram | currency | `rpc.service="hipstershop.CurrencyService"`, `rpc.method`, `rpc.grpc_status_code` | Currency SLI |
| `app.currency.conversions` | Counter | currency | `app.currency.from`, `app.currency.to` | Currency usage analytics |
| `app.currency.exchange_rate` | Gauge | currency | `app.currency.from`, `app.currency.to` | Rate staleness monitoring |

**Histogram bucket alignment for CUP 6 latency SLO (P95 < 100 ms):**
```
buckets: [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5]
```

#### 4.6.3 Error & Failure Semantics

| Condition | Span Status | Error Count | Notes |
|---|---|---|---|
| gRPC INTERNAL error | `ERROR` | ✅ Count | High impact — affects all users |
| Unknown currency code (invalid input) | `UNSET` | ❌ Exclude | User/config error |
| Rate table not loaded at startup | `ERROR` | ✅ Count | Startup failure — alert immediately |

---

### CUP 7 — AI Product Assistant

**Priority:** P7 | **Availability SLO:** 99.0% | **P95 Latency:** < 10,000 ms

#### 4.7.1 Tracing Plan

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `POST /api/product-ask-ai-assistant/{productId}` | frontend | Server | — (root) | `http.route`, `http.response_status_code`, `app.product.id` |
| `hipstershop.ProductCatalogService/GetProduct` | product-catalog | Server | frontend | `app.product.id` |
| `POST /v1/chat/completions` | llm | Server | frontend | `app.llm.model`, `app.llm.prompt_tokens`, `app.llm.completion_tokens`, `app.llm.total_tokens` |
| `llm.inference` | llm | Internal | POST /v1/chat/completions | `app.llm.duration_ms`, `app.llm.finish_reason` |

**LLM-specific attributes:** Do NOT include user question text or product description content in span attributes (potential PII and excessive data). Use token counts and model identifiers only.

#### 4.7.2 Metrics Plan

| Metric Name | Type | Service | Labels | SLO Purpose |
|---|---|---|---|---|
| `http_server_request_duration_seconds` | Histogram | llm | `http.route="/v1/chat/completions"`, `http.response_status_code` | LLM availability + latency SLI |
| `app.llm.requests` | Counter | llm | `app.llm.model`, `app.llm.status` | LLM request rate |
| `app.llm.tokens` | Counter | llm | `app.llm.model`, `app.llm.token_type` (prompt/completion) | Token consumption |
| `app.llm.inference.duration` | Histogram | llm | `app.llm.model` | Inference latency |

**Histogram bucket alignment for CUP 7 latency SLO (P95 < 10,000 ms):**
```
buckets: [0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]
```

#### 4.7.3 Error & Failure Semantics

| Condition | Span Status | Error Count | Notes |
|---|---|---|---|
| LLM service 5xx | `ERROR` | ✅ Count | Counts against SLO budget |
| LLM timeout > 20 s | `ERROR` | ✅ Count | Record `app.llm.timeout=true` |
| LLM returns empty response | `ERROR` | ✅ Count | Business error |
| Product not found (cannot provide context) | `ERROR` | ✅ Count | Upstream dependency failure |
| Graceful degradation (UI shows error) | `ERROR` | ✅ Count | SLO budget has 7.2 hr/month buffer |

---

### CUP 8 — Product Reviews

**Priority:** P8 | **Availability SLO:** 99.5% | **P95 Latency:** < 500 ms

#### 4.8.1 Tracing Plan

| Span Name | Service | Kind | Parent | Key Attributes |
|---|---|---|---|---|
| `GET /api/product-reviews/{productId}` | frontend | Server | — (root) | `http.route`, `http.response_status_code`, `app.product.id` |
| `GET /api/product-reviews-avg-score/{productId}` | frontend | Server | — (root) | `http.route`, `app.product.id` |
| `POST /api/product-reviews/{productId}` | frontend | Server | — (root) | `http.route` |
| `oteldemo.ProductReviewService/ListProductReviews` | product-reviews | Server | frontend | `app.product.id`, `app.reviews.count`, `app.reviews.page` |
| `oteldemo.ProductReviewService/GetProductReviewsAvgScore` | product-reviews | Server | frontend | `app.product.id`, `app.reviews.avg_score` |
| `oteldemo.ProductReviewService/CreateProductReview` | product-reviews | Server | frontend | `app.product.id`, `app.reviews.score` (no review text) |
| `db.postgresql.query` | product-reviews | Client | gRPC handler | `db.system="postgresql"`, `db.operation`, `db.sql.table="reviews"` (no query parameters) |

#### 4.8.2 Metrics Plan

| Metric Name | Type | Service | Labels | SLO Purpose |
|---|---|---|---|---|
| `http_server_request_duration_seconds` | Histogram | frontend | `http.route`, `http.response_status_code` | Reviews availability + latency SLI |
| `rpc_server_duration` | Histogram | product-reviews | `rpc.service`, `rpc.method`, `rpc.grpc_status_code` | Reviews gRPC SLI |
| `db.client.operation.duration` | Histogram | product-reviews | `db.system`, `db.operation` | PostgreSQL query latency |
| `app.reviews.submitted` | Counter | product-reviews | — | Review creation rate |
| `app.reviews.score.distribution` | Histogram | product-reviews | `app.product.id` (keep cardinality bounded) | Score distribution |

#### 4.8.3 Error & Failure Semantics

| Condition | Span Status | Error Count | Notes |
|---|---|---|---|
| PostgreSQL connection failure | `ERROR` | ✅ Count | Service degraded |
| PostgreSQL query timeout | `ERROR` | ✅ Count | Performance issue |
| Review not found (404) | `UNSET` | ❌ Exclude | Normal state for new products |
| Review submission duplicate (409) | `UNSET` | ❌ Exclude | Business constraint |
| gRPC INTERNAL | `ERROR` | ✅ Count | Service error |

---

## 5. OTel SDK Standards

This section defines **platform-wide conventions** that all services must adhere to, regardless of language.

### 5.1 Required SDK Packages by Language

#### Go (checkout, product-catalog)
```
go.opentelemetry.io/otel                       v1.35+
go.opentelemetry.io/otel/sdk                   v1.35+
go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc
go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc
go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc
go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc
go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp
go.opentelemetry.io/contrib/bridges/otelslog
go.opentelemetry.io/contrib/instrumentation/runtime
```

#### TypeScript / Next.js (frontend)
```
@opentelemetry/sdk-node
@opentelemetry/api
@opentelemetry/auto-instrumentations-node
@opentelemetry/exporter-trace-otlp-grpc
@opentelemetry/exporter-metrics-otlp-grpc
@opentelemetry/sdk-metrics
@opentelemetry/resources
@opentelemetry/semantic-conventions
```

#### C# / .NET 8 (cart, accounting)
```
OpenTelemetry                                  1.11+
OpenTelemetry.Exporter.OpenTelemetryProtocol
OpenTelemetry.Extensions.Hosting
OpenTelemetry.Instrumentation.AspNetCore
OpenTelemetry.Instrumentation.Http
OpenTelemetry.Instrumentation.GrpcNetClient
OpenTelemetry.Instrumentation.Runtime
OpenTelemetry.Instrumentation.StackExchangeRedis   (cart only)
```

#### Java / Kotlin (ad, fraud-detection)
```
# Use Java agent: opentelemetry-javaagent-2.25.jar (auto-instrumentation)
# For manual instrumentation:
io.opentelemetry:opentelemetry-api:1.48+
io.opentelemetry:opentelemetry-sdk:1.48+
io.opentelemetry:opentelemetry-exporter-otlp:1.48+
io.opentelemetry.instrumentation:opentelemetry-spring-boot-starter  (ad)
io.opentelemetry.instrumentation:opentelemetry-kafka-clients-2.6    (fraud-detection)
```

#### Python (recommendation, llm, product-reviews)
```
opentelemetry-api>=1.30
opentelemetry-sdk>=1.30
opentelemetry-exporter-otlp-proto-grpc>=1.30
opentelemetry-instrumentation-grpc
opentelemetry-instrumentation-fastapi  (llm)
opentelemetry-instrumentation-flask    (if applicable)
opentelemetry-instrumentation-requests
opentelemetry-instrumentation-psycopg2 (product-reviews)
```

#### Ruby (email)
```
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp
opentelemetry-instrumentation-sinatra
opentelemetry-instrumentation-net_http
opentelemetry-instrumentation-rack
```

#### PHP (quote)
```
open-telemetry/sdk
open-telemetry/opentelemetry-auto-slim         (or auto-laravel)
open-telemetry/exporter-otlp
open-telemetry/opentelemetry-auto-http-client
```

#### Rust (shipping)
```
opentelemetry = "0.28"
opentelemetry-otlp = "0.28"
opentelemetry_sdk = "0.28"
opentelemetry-http = "0.28"
tracing-opentelemetry = "0.29"
tracing = "0.1"
```

#### C++ (currency)
```
opentelemetry-cpp v1.19+
  - opentelemetry-exporter-otlp-grpc
  - opentelemetry-ext-grpc  (gRPC server instrumentation)
```

### 5.2 ActivitySource / Tracer Naming Convention

All tracers must follow the naming pattern: `{service-name}` in snake_case, matching the `service.name` resource attribute.

| Service | Tracer Name |
|---|---|
| frontend | `frontend` |
| checkout | `checkout` |
| cart | `cart` |
| payment | `payment` |
| currency | `currency` |
| product-catalog | `product_catalog` |
| quote | `quote` |
| shipping | `shipping` |
| email | `email` |
| accounting | `accounting` |
| fraud-detection | `fraud_detection` |
| recommendation | `recommendation` |
| ad | `ad` |
| llm | `llm` |
| product-reviews | `product_reviews` |

### 5.3 Resource Attributes (Mandatory for All Services)

All services must export the following resource attributes on every telemetry signal:

```yaml
service.name: "{service-folder-name}"         # e.g., "checkout"
service.version: "${SERVICE_VERSION:-dev}"     # from env
service.namespace: "astronomy-shop"
deployment.environment: "${DEPLOYMENT_ENV:-development}"
host.name: "${HOSTNAME}"
```

These attributes enable filtering in Jaeger, Prometheus, and Grafana across all CUPs.

### 5.4 Auto-Instrumentation Requirements

#### HTTP Client (outbound)
All services making outbound HTTP calls must wrap their HTTP client:
- **Go:** `otelhttp.NewTransport(http.DefaultTransport)` ✅ (already in checkout)
- **Node.js:** `@opentelemetry/instrumentation-http` via auto-instrumentation
- **Python:** `opentelemetry-instrumentation-requests` or `httpx`
- **Ruby:** `opentelemetry-instrumentation-net_http`
- **PHP:** `opentelemetry-auto-http-client`
- **Rust:** Inject TraceContext headers manually via `opentelemetry-http`

#### gRPC Server (inbound)
All gRPC servers must install the server interceptor/handler:
- **Go:** `grpc.StatsHandler(otelgrpc.NewServerHandler())` ✅ (already in checkout)
- **C# / .NET:** `AddOpenTelemetry().WithTracing(b => b.AddGrpcServerInstrumentation())`
- **Java/Kotlin:** Java agent handles this automatically
- **Python:** `opentelemetry-instrumentation-grpc`
- **C++:** `opentelemetry-ext-grpc` server interceptor

#### gRPC Client (outbound)
- **Go:** `grpc.WithStatsHandler(otelgrpc.NewClientHandler())` ✅ (already in checkout)
- **C# / .NET:** `AddOpenTelemetry().WithTracing(b => b.AddGrpcClientInstrumentation())`
- **Java:** Java agent handles automatically
- **Python:** `opentelemetry-instrumentation-grpc` client interceptor

#### Database Access
- **Valkey / Redis (cart, C#):** `OpenTelemetry.Instrumentation.StackExchangeRedis`
- **PostgreSQL (product-reviews, Python):** `opentelemetry-instrumentation-psycopg2`
- **PostgreSQL (checkout, Go):** `otelsql` or `otelgorm` wrapping the driver

### 5.5 Mandatory Span Attributes

#### HTTP Requests (OTel Semconv v1.24)

| Attribute | Type | Example | Required |
|---|---|---|---|
| `http.request.method` | string | `POST` | ✅ |
| `url.scheme` | string | `http` | ✅ |
| `http.route` | string | `/api/checkout` | ✅ |
| `http.response.status_code` | int | `200` | ✅ |
| `server.address` | string | `frontend` | ✅ |
| `url.path` (client only) | string | `/api/checkout` | ✅ |
| `network.protocol.version` | string | `1.1` | Recommended |

#### gRPC Requests (OTel Semconv v1.24)

| Attribute | Type | Example | Required |
|---|---|---|---|
| `rpc.system` | string | `grpc` | ✅ |
| `rpc.service` | string | `hipstershop.CheckoutService` | ✅ |
| `rpc.method` | string | `PlaceOrder` | ✅ |
| `rpc.grpc.status_code` | int | `0` | ✅ |

#### Business Context Attributes

These attributes must be added via **manual instrumentation** on the relevant spans:

| Attribute | Type | CUPs | Service | Notes |
|---|---|---|---|---|
| `app.user.id` | string | 1, 3 | checkout, cart | Session/user ID — not email |
| `app.user.currency` | string | 1, 2, 6 | checkout, frontend | ISO-4217 currency code |
| `app.order.id` | string | 1, 4 | checkout | UUID, safe to log |
| `app.order.amount` | float64 | 1 | checkout | Total order value |
| `app.order.items.count` | int | 1 | checkout | Number of distinct items |
| `app.payment.transaction.id` | string | 1 | payment | Safe transaction ID |
| `app.payment.card_type` | string | 1 | payment | `visa`, `mastercard` |
| `app.payment.charged` | bool | 1 | payment | False for synthetic requests |
| `app.shipping.tracking.id` | string | 1, 4 | checkout, shipping | Shipment tracking ID |
| `app.product.id` | string | 2, 7, 8 | product-catalog | Product UUID |
| `app.product.category` | string | 2 | product-catalog | Category name |
| `app.cart.items.count` | int | 1, 3 | cart | Items in cart |
| `app.llm.model` | string | 7 | llm | Model identifier |
| `app.llm.total_tokens` | int | 7 | llm | Total tokens consumed |
| `app.fraud.decision` | string | 4 | fraud-detection | `allow`, `flag`, `block` |

#### Kafka Messaging Attributes (OTel Semconv v1.24)

| Attribute | Type | Required |
|---|---|---|
| `messaging.system` | `kafka` | ✅ |
| `messaging.destination.name` | `orders` | ✅ |
| `messaging.operation` | `publish` / `process` | ✅ |
| `messaging.consumer.group.name` | e.g., `accounting-service` | ✅ for consumers |
| `messaging.message.id` | message key/offset | Recommended |
| `messaging.kafka.message.offset` | int | Recommended |
| `messaging.kafka.destination.partition` | int | Recommended |

### 5.6 Propagation Standard

All services must use **W3C TraceContext + Baggage** propagation:

```
traceparent: 00-{traceId}-{spanId}-{flags}
tracestate: {vendor-specific}
baggage: synthetic_request=true (for load generator / canary requests)
```

Services must configure the composite propagator:
- **Go:** `propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{})` ✅
- **Node.js:** `W3CTraceContextPropagator` + `W3CBaggagePropagator`
- **Python:** `TraceContextTextMapPropagator` + `W3CBaggagePropagator`
- **C#:** `Propagators.DefaultTextMapPropagator` (includes both by default)

Synthetic traffic from the load generator must inject `baggage: synthetic_request=true`. All services reading this baggage must exclude those spans from SLO calculations by setting attribute `synthetic_request=true` on the span.

### 5.7 OTLP Export Configuration (Standard for All Services)

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_SERVICE_NAME={service-name}
OTEL_RESOURCE_ATTRIBUTES=service.namespace=astronomy-shop,deployment.environment=${ENV}
OTEL_TRACES_SAMPLER=parentbased_traceidratio   # see Section 7
OTEL_TRACES_SAMPLER_ARG={sampling_ratio}       # see Section 7
OTEL_METRICS_EXPORT_INTERVAL=30000             # 30 seconds
OTEL_LOGS_EXPORTER=otlp
```

### 5.8 PII & Security Rules

| Data Type | Action | Enforcement Point |
|---|---|---|
| Credit card number (PAN) | **NEVER** in traces/logs/metrics | Code review gate; OTel Collector sanitize_spans processor |
| CVV / CVC | **NEVER** in traces/logs/metrics | Code review gate |
| User email address | **NEVER** as span attribute; OK in structured logs with masking | Log processor must mask `email` fields |
| User full name | **NEVER** as span attribute | Code review gate |
| Password / token | **NEVER** anywhere | Code review gate; secret scanner in CI |
| Last 4 digits of card | Allowed with explicit review | Document per service |
| User session ID | Allowed as `app.user.id` | Non-PII identifier |
| Order ID | Allowed | Safe UUID |
| Transaction ID | Allowed | Safe UUID |
| IP address | Allowed in HTTP semconv | Part of standard HTTP attributes |
| LLM prompt/response text | **NEVER** in spans; OK in logs with explicit consent | LLM service code review |

**OTel Collector sanitise processor** (add to `otel-collector/otelcol-config.yml`):
```yaml
processors:
  transform/sanitize_spans:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          - delete_key(attributes, "credit_card_number")
          - delete_key(attributes, "credit_card_cvv")
          - delete_key(attributes, "app.user.email")
          - replace_all_patterns(attributes, "value", "\\b\\d{13,19}\\b", "****")
```

---

## 6. Rollout & Migration Plan

### 6.1 Phased Rollout by CUP Priority

#### Phase 1 — Revenue Path (Week 1–3) — CUP 1, CUP 3

**Objective:** Full trace coverage and SLI-grade metrics on all revenue-touching services.

| Service | Language | Instrumentation Tasks | Definition of Done |
|---|---|---|---|
| **frontend** | TypeScript | Add `app.user.currency`, `app.order.id` to checkout span; add metrics counter for orders; validate `InstrumentationMiddleware` propagates W3C context | `app.order.id` visible on checkout spans in Jaeger; `app.orders.placed` counter in Prometheus |
| **checkout** | Go | ✅ Baseline exists. Add `app.order.amount` histogram; validate Kafka header propagation | `app.order.amount` histogram in Prometheus; Kafka spans linked correctly in Jaeger |
| **payment** | Node.js | Add `app.payment.duration` histogram; add `app.payment.status` label to counter | `app.payment.transactions` counter with status label visible |
| **cart** | C# | Add `otelgrpc` server handler; add Valkey `StackExchangeRedis` instrumentation; add metrics | Cart gRPC spans visible in Jaeger; `rpc_server_duration` for `hipstershop.CartService` in Prometheus |
| **currency** | C++ | Full SDK setup with `opentelemetry-cpp`; gRPC server interceptor | Currency spans visible; `rpc_server_duration` metric exported |
| **quote** | PHP | Full SDK setup; HTTP auto-instrumentation; W3C context extraction | Quote spans visible with correct parent from checkout |
| **shipping** | Rust | Full SDK setup; HTTP server instrumentation; `tracing-opentelemetry` | Shipping spans visible; `rpc_server_duration` for `ShipOrder` exported |
| **email** | Ruby | Full SDK setup; Sinatra instrumentation | Email spans visible in Jaeger |

**Validation Steps for Phase 1:**
1. Generate a test checkout via the load generator.
2. Open Jaeger — verify end-to-end trace from `POST /api/checkout` through all 7 services with no broken spans.
3. Open Prometheus — verify presence of `http_server_request_duration_seconds` for `/api/checkout` and `rpc_server_duration` for `hipstershop.CheckoutService/PlaceOrder`.
4. Compute CUP 1 SLI expressions from `CRITICAL_USER_PATHS_SLO.md` — verify they return a value (not `NaN`).
5. Verify no PII attributes in any checkout-related span using the Jaeger search UI.

---

#### Phase 2 — Browse & Cart Completion (Week 4–5) — CUP 2, CUP 5, CUP 6

**Objective:** Full trace coverage for browse, shipping quote, and currency paths.

| Service | Language | Instrumentation Tasks | Definition of Done |
|---|---|---|---|
| **product-catalog** | Go | Add `otelgrpc` server handler; add `app.products.count` gauge; add cache hit/miss counter | `rpc_server_duration` for `hipstershop.ProductCatalogService` in Prometheus |
| **recommendation** | Python | Add `opentelemetry-instrumentation-grpc`; add `app.recommendation.result_count` span attribute | Recommendation spans visible with parent from frontend |
| **ad** | Java | Verify Java agent v2.25 captures all spans; add `app.ad.count` counter | Ad spans visible in Jaeger; JVM metrics in Prometheus |
| **quote** | PHP | *(Carried over from Phase 1 if not completed)* | Quote spans in Jaeger |

**Validation Steps for Phase 2:**
1. Verify `GET /api/products` trace shows product-catalog and currency as child spans.
2. Verify `GET /api/recommendations` trace shows recommendation service span.
3. Compute CUP 2, CUP 5, CUP 6 SLI expressions — verify they return a value.

---

#### Phase 3 — Async Fulfillment & Compliance (Week 6–7) — CUP 4

**Objective:** Kafka consumer tracing and consumer lag metrics for compliance paths.

| Service | Language | Instrumentation Tasks | Definition of Done |
|---|---|---|---|
| **accounting** | C# | Add Kafka consumer span extraction (W3C from headers); add `app.kafka.consumer.lag` gauge via Kafka metrics JMX exporter or consumer group offset polling; log structured events | Accounting consumer spans linked to checkout producer span in Jaeger |
| **fraud-detection** | Kotlin | Add Kafka consumer `opentelemetry-kafka-clients-2.6`; add `app.fraud.decision` span attribute; add fraud counter metric | Fraud-detection spans linked to checkout spans; `app.fraud.assessments` counter visible |
| **kafka** (broker metrics) | JMX | Configure Kafka JMX exporter to expose `kafka_consumer_group_lag` | `kafka_consumer_group_lag` metric available in Prometheus for both consumer groups |

**Validation Steps for Phase 3:**
1. In Jaeger, trace a checkout order — navigate to the producer span and verify links to accounting and fraud consumer spans.
2. In Prometheus, verify `kafka_consumer_group_lag{group="accounting-service"}` and `{group="fraud-detection-service"}` are present and < their SLO thresholds under normal load.

---

#### Phase 4 — Non-Blocking Paths (Week 8–9) — CUP 7, CUP 8

**Objective:** Instrumentation for LLM and reviews — lower priority but still SLO-tracked.

| Service | Language | Instrumentation Tasks | Definition of Done |
|---|---|---|---|
| **llm** | Python | Add `opentelemetry-instrumentation-fastapi` (or Flask); add `app.llm.tokens` counter; add inference duration histogram | LLM spans visible; token counter in Prometheus |
| **product-reviews** | Python | Full SDK setup; `opentelemetry-instrumentation-grpc` + `opentelemetry-instrumentation-psycopg2`; add review counters | Reviews gRPC spans visible; PostgreSQL spans present |
| **postgresql** | N/A | PostgreSQL exporter for `pg_stat_statements` to Prometheus | DB query latency visible as infrastructure metric |

---

### 6.2 Shared Observability Bootstrap Libraries

To avoid duplicating SDK initialisation across 17 services, define **one bootstrap function per language group**:

| Library Name | Language Group | Services | Provides |
|---|---|---|---|
| `otel-bootstrap-go` | Go | checkout, product-catalog | TracerProvider, MeterProvider, LoggerProvider, OTLP gRPC exporter, resource detection |
| `otel-bootstrap-dotnet` | C# / .NET | cart, accounting | `IServiceCollection` extension method; all providers; gRPC + Redis + ASP.NET Core instrumentation |
| `otel-bootstrap-python` | Python | recommendation, llm, product-reviews | `configure_otel(service_name)` function; gRPC + HTTPX + DB instrumentation |
| `otel-bootstrap-jvm` | Java/Kotlin | ad, fraud-detection | Java agent `-javaagent` configuration; agent config file |
| (per-service) | Node.js | payment, frontend | Each service owns its bootstrap; share common config pattern |
| (per-service) | Ruby/PHP/Rust/C++ | email, quote, shipping, currency | Individual setup; no cross-service sharing practical |

### 6.3 Feature Flags for Instrumentation Control

Use the existing FlagD infrastructure to gate high-overhead instrumentation:

```json
{
  "flags": {
    "otel.checkout.detailed_tracing": {
      "state": "ENABLED",
      "variants": { "on": true, "off": false },
      "defaultVariant": "on"
    },
    "otel.browse.sampling_rate": {
      "state": "ENABLED",
      "variants": { "full": 1.0, "reduced": 0.1 },
      "defaultVariant": "reduced"
    },
    "otel.llm.trace_enabled": {
      "state": "ENABLED",
      "variants": { "on": true, "off": false },
      "defaultVariant": "on"
    }
  }
}
```

---

## 7. Sampling Strategy

### 7.1 Sampling Policy by CUP

| CUP | Priority | Sampling Approach | Head Ratio | Tail Policy | Rationale |
|---|---|---|---|---|---|
| CUP 1 — Checkout | P1 | **Always-on** | 100% | N/A | Revenue path; every transaction must be traceable |
| CUP 3 — Cart | P1 | **Always-on** | 100% | N/A | Directly gates CUP 1; full coverage required |
| CUP 6 — Currency | P1 | **Always-on** | 100% | N/A | Universal dependency; called on every page |
| CUP 4 — Fulfillment | P4 | **Always-on** | 100% | N/A | Compliance-critical; every order event must be traced |
| CUP 5 — Shipping Quote | P5 | **Always-on** | 100% | N/A | Synchronous checkout blocker |
| CUP 2 — Browse | P2 | **Tail sampling** | 100% ingest | Retain: errors + slow > P95; Drop: 90% of fast happy paths | High volume; most browse requests are identical; errors and slow outliers must be kept |
| CUP 8 — Reviews | P8 | **Head sampling** | 25% | N/A | Low priority; 25% sufficient for latency profiling |
| CUP 7 — AI Assistant | P7 | **Head sampling** | 50% | N/A | Moderate; each inference is slow so storage cost is high |

### 7.2 Sampling Configuration

#### Head-Based Sampling (services)

Set via `OTEL_TRACES_SAMPLER` environment variable per service:

```bash
# Always-on services (checkout, cart, currency, quote, shipping, accounting, fraud-detection)
OTEL_TRACES_SAMPLER=parentbased_always_on

# Browse services (product-catalog, recommendation, ad)
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.10    # 10% head sample for browse

# Reviews
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.25

# LLM
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.50
```

**Important:** The **frontend BFF is the trace root** for all browser-initiated paths. The `parentbased_` prefix ensures all downstream services respect the sampling decision made at the root. Do not set `traceidratio` on downstream services independently — this would break trace completeness.

#### Tail-Based Sampling (OTel Collector — for Browse path)

Configure the tail sampling processor in `otel-collector/otelcol-config.yml` for the browse path:

```yaml
processors:
  tail_sampling/browse:
    decision_wait: 10s
    num_traces: 50000
    expected_new_traces_per_sec: 100
    policies:
      # Always keep error traces
      - name: error-policy
        type: status_code
        status_code: {status_codes: [ERROR]}
      # Keep slow traces (> 800ms = P95 threshold for CUP 2)
      - name: latency-policy
        type: latency
        latency: {threshold_ms: 800}
      # Keep a random 10% sample of healthy traces
      - name: probabilistic-policy
        type: probabilistic
        probabilistic: {sampling_percentage: 10}
```

### 7.3 High-Volume Endpoint Handling

| Endpoint | Estimated RPS | Risk | Mitigation |
|---|---|---|---|
| `GET /api/products` | High (all page loads) | High span volume | Tail sample at 10%; head sample product-catalog at 10% |
| `GET /api/currency` | Very High (all page loads × items) | Very high span volume | Auto-instrumented by gRPC handler only; no manual child spans |
| `GET /images/*` | Extremely High (CDN-able) | Noise | Exclude from OTel; nginx metrics only |
| `POST /api/checkout` | Moderate (purchase rate) | Revenue-critical | Always-on; never sample |
| `POST /v1/chat/completions` | Low (explicit user action) | High storage per span | 50% head sample |

### 7.4 Error Budget Burning Rate Alerting

The following alert conditions require **full (unsampled) trace data** to be effective. Do not sample these trace routes:

- Any `http.response.status_code = 5xx` on `/api/checkout` — burn rate alert on error budget.
- Any `rpc.grpc.status_code != 0` on `hipstershop.CartService` or `hipstershop.CheckoutService`.
- Kafka consumer lag > 1000 messages for accounting or fraud-detection.

---

## 8. Risks & Guardrails

### 8.1 Cardinality Traps

**Risk:** High-cardinality labels on metrics destroy Prometheus memory and query performance.

| Anti-pattern | Impact | Guardrail |
|---|---|---|
| `app.user.id` as a metric label | 1 series per user = millions of series | **NEVER** use user IDs as metric labels. Use in spans only. |
| `app.product.id` as a metric label on high-volume metrics | 1 series per product × request type | Allowed only on low-volume review metrics; prohibited on browse metrics |
| `url.full` or `http.target` as a metric label | 1 series per unique URL with dynamic segments | Always use `http.route` (templated) not `url.full` |
| `app.order.id` as a metric label | 1 series per order = unbounded cardinality | Spans only, never metrics |
| Unbounded `error_message` labels | String cardinality explosion | Use `error_type` (enum) instead of free-text error messages |
| Dynamic `session_id` as label | Unbounded | Session context in baggage/spans only |

**Prometheus cardinality budget:** No single metric should exceed 10,000 unique label combinations. Review all new metrics during code review with this constraint.

### 8.2 Over-Instrumentation Risks

| Risk | Example | Impact | Mitigation |
|---|---|---|---|
| Spans on every function call | Adding `tracer.Start` to utility functions | Trace storage cost; noise in Jaeger | Instrument at service boundary and business operation level only |
| Logging span attributes redundantly | Writing the same data to both span attributes and log fields in the same service | Double storage cost | Choose one: prefer spans for operational data; logs for audit |
| Manual span creation inside auto-instrumented paths | Creating a child span manually inside a gRPC handler that the auto-instrumenter already spans | Duplicate spans; confusion | Check if the framework auto-instruments before adding manual spans |
| LLM prompt content in spans | Storing full user questions in `app.llm.prompt` attribute | Storage explosion; PII risk | Token counts only; never store prompt/response text in spans |
| Nested Valkey call spans inside every cart operation | Sub-1ms DB calls generating spans | High overhead on hot path | Auto-instrumentation only; no additional child spans on Valkey calls |

### 8.3 Partial Trace Anti-Patterns

| Anti-pattern | Risk | Prevention |
|---|---|---|
| Service not propagating `traceparent` header on outbound calls | Trace breaks at service boundary; SLI queries return wrong results | Mandatory: all HTTP clients use OTel-instrumented transport; all gRPC clients use `otelgrpc` handler |
| Kafka consumer creating child span instead of linked span | Merges async processing latency into the synchronous order response trace | Always use `tracer.Start` with `WithLinks(...)` for Kafka consumers; never use the producer context as parent |
| Frontend BFF creating spans without extracting W3C context from browser | Browser-originated traces are disconnected from server traces | Ensure `InstrumentationMiddleware` in frontend extracts `traceparent` from incoming requests |
| Context not passed through async goroutines / threads | Spans appear as root spans with no parent | Always pass `ctx` through goroutine chains; use `context.WithValue` appropriately |
| gRPC client not using `otelgrpc` handler | Client-side spans missing; only server-side spans visible | All `grpc.Dial` / `grpc.NewClient` calls must use `grpc.WithStatsHandler(otelgrpc.NewClientHandler())` |

### 8.4 Inconsistent Naming Risks

| Risk | Example | Impact | Prevention |
|---|---|---|---|
| Span name includes dynamic segments | `"GET /api/products/telescope-sku-123"` | High-cardinality trace search; query failure | Span names must use template form: `"GET /api/products/{productId}"` |
| Mixed semconv versions | Service A uses `http.url`, service B uses `url.full` | SLI queries fail on one service | Pin all services to OTel semconv v1.24; enforce in bootstrap library |
| Custom attribute names duplicating semconv | `"product.id"` vs `"app.product.id"` | Duplicate data; confusing dashboards | `app.*` namespace for business attributes; `semconv.*` for standard attributes — never mix |
| Different metric names per service for the same concept | `orders_placed` in checkout vs `placed_orders` in frontend | Cannot aggregate across services | Define metric registry in this document; enforce in code review |
| Inconsistent gRPC service name in metrics | `CheckoutService` vs `hipstershop.CheckoutService` | SLI queries using specific service names break | Use fully-qualified proto package name always |

### 8.5 Logging Sensitive Data in Telemetry

| Risk | Specific Scenario | Prevention |
|---|---|---|
| Email address in checkout log | `logger.Info("Sending confirmation to user@email.com")` | Use `app.user.id` in log; mask email |
| Credit card in payment debug log | Logging the `ChargeRequest` struct | Never log request structs containing `CreditCardInfo`; log only `transactionId` |
| LLM question in inference log | Logging user input to `POST /v1/chat/completions` | Log token counts and model only |
| Stack trace with SQL query containing user data | ORM exception logs | Configure log sanitizer in OTel log processor |
| Bearer tokens in HTTP headers | Logging full `Authorization` header in debug mode | Exclude `Authorization`, `Cookie`, `Set-Cookie` headers from span attributes |

**OTel Collector protection layer:** Even with SDK-level guardrails, configure a `transform` processor in the collector as a defence-in-depth layer to delete known PII attributes before they reach Jaeger or OpenSearch.

### 8.6 Production Performance Guardrails

| Guardrail | Specification |
|---|---|
| Maximum span attribute value length | 256 characters (configure `OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT=256`) |
| Maximum spans per trace | 1,000 (configure `OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT=64`, `OTEL_SPAN_EVENT_COUNT_LIMIT=16`) |
| Metric export interval | 30 seconds minimum (avoid 5-second intervals in production) |
| Trace export batch size | 512 spans per batch; timeout 5 seconds |
| Memory limiter on OTel Collector | 75% of allocated memory; spike limit 25% |
| SDK overhead budget | < 1% CPU, < 50 MB RSS per service at P99 load |

---

## 9. Appendix: Code Examples

### 9.1 Go — Manual Span Creation (checkout pattern)

```go
// In a gRPC handler or internal function:
func (cs *checkout) quoteShipping(ctx context.Context, address *pb.Address, items []*pb.CartItem) (*pb.Money, error) {
    ctx, span := tracer.Start(ctx, "quoteShipping",
        trace.WithSpanKind(trace.SpanKindInternal),
        trace.WithAttributes(
            attribute.Int("app.quote.items_count", len(items)),
            attribute.String("app.quote.address.country", address.GetCountry()),
        ),
    )
    defer span.End()

    // ... business logic ...

    // Record result
    span.SetAttributes(
        attribute.Float64("app.quote.cost_usd", cost),
    )
    return result, nil
}
```

### 9.2 Go — Custom Metric Emission (checkout pattern)

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/metric"
)

var (
    meter         = otel.GetMeterProvider().Meter("checkout")
    ordersCounter metric.Int64Counter
    orderAmount   metric.Float64Histogram
)

func init() {
    var err error
    ordersCounter, err = meter.Int64Counter(
        "app.orders.placed",
        metric.WithDescription("Total number of orders placed"),
        metric.WithUnit("{order}"),
    )
    if err != nil { /* handle */ }

    orderAmount, err = meter.Float64Histogram(
        "app.order.amount",
        metric.WithDescription("Order total amount"),
        metric.WithUnit("USD"),
        metric.WithExplicitBucketBoundaries(10, 25, 50, 100, 200, 500, 1000, 2000),
    )
    if err != nil { /* handle */ }
}

// In PlaceOrder, after successful order:
func recordOrderMetrics(ctx context.Context, currency string, amount float64) {
    attrs := metric.WithAttributes(
        attribute.String("app.user.currency", currency),
        attribute.String("app.order.status", "success"),
    )
    ordersCounter.Add(ctx, 1, attrs)
    orderAmount.Record(ctx, amount, attrs)
}
```

### 9.3 Node.js — Manual Span and Counter (payment pattern)

```javascript
const { trace, metrics, context, SpanStatusCode } = require('@opentelemetry/api');

const tracer = trace.getTracer('payment');
const meter = metrics.getMeter('payment');

// Histogram for charge duration
const chargeDurationHist = meter.createHistogram('app.payment.charge.duration', {
    description: 'Duration of payment charge calls in milliseconds',
    unit: 'ms',
    advice: {
        explicitBucketBoundaries: [50, 100, 200, 300, 500, 800, 1000, 1500, 3000],
    },
});

const transactionsCounter = meter.createCounter('app.payment.transactions', {
    description: 'Total payment transactions',
    unit: '{transaction}',
});

async function charge(request) {
    const span = tracer.startActiveSpan('charge', async (span) => {
        const startMs = Date.now();
        try {
            // ... charge logic ...

            const durationMs = Date.now() - startMs;
            chargeDurationHist.record(durationMs, {
                'app.payment.card_type': cardType,
                'app.payment.status': 'success',
            });
            transactionsCounter.add(1, {
                'app.payment.currency': request.amount.currencyCode,
                'app.payment.card_type': cardType,
                'app.payment.status': 'success',
            });

            span.setStatus({ code: SpanStatusCode.OK });
            span.end();
            return { transactionId };
        } catch (err) {
            span.recordException(err);
            span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
            transactionsCounter.add(1, {
                'app.payment.currency': request.amount.currencyCode,
                'app.payment.status': 'error',
                'app.payment.error_type': err.name,
            });
            span.end();
            throw err;
        }
    });
}
```

### 9.4 C# / .NET — ActivitySource Setup (cart pattern)

```csharp
using System.Diagnostics;
using System.Diagnostics.Metrics;
using OpenTelemetry;
using OpenTelemetry.Trace;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;

// Shared ActivitySource and Meter for the service
public static class CartTelemetry
{
    public static readonly ActivitySource ActivitySource = new("cart", "1.0.0");
    public static readonly Meter Meter = new("cart", "1.0.0");

    // Metrics
    public static readonly Counter<long> CartItemsAdded =
        Meter.CreateCounter<long>("app.cart.items.added",
            unit: "{item}",
            description: "Total items added to carts");

    public static readonly Histogram<double> CartItemCount =
        Meter.CreateHistogram<double>("app.cart.items.count",
            unit: "{item}",
            description: "Number of items in cart");
}

// In CartService.cs
public override async Task<Empty> AddItem(AddItemRequest request, ServerCallContext context)
{
    using var activity = CartTelemetry.ActivitySource.StartActivity("AddItem");
    activity?.SetTag("app.cart.item.product_id", request.Item.ProductId);
    activity?.SetTag("app.cart.item.quantity", request.Item.Quantity);

    try
    {
        await _cartStore.AddItemAsync(request.UserId, request.Item.ProductId, request.Item.Quantity);

        CartTelemetry.CartItemsAdded.Add(1);

        return new Empty();
    }
    catch (Exception ex)
    {
        activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
        activity?.RecordException(ex);
        throw;
    }
}

// In Program.cs / Startup — bootstrap configuration
builder.Services
    .AddOpenTelemetry()
    .ConfigureResource(r => r
        .AddService(serviceName: "cart", serviceVersion: "1.0.0")
        .AddAttributes(new Dictionary<string, object>
        {
            ["service.namespace"] = "astronomy-shop",
            ["deployment.environment"] = Environment.GetEnvironmentVariable("DEPLOYMENT_ENV") ?? "development"
        }))
    .WithTracing(t => t
        .AddSource("cart")
        .AddAspNetCoreInstrumentation()
        .AddGrpcClientInstrumentation()
        .AddRedisInstrumentation()                    // Valkey/StackExchange.Redis
        .AddOtlpExporter())
    .WithMetrics(m => m
        .AddMeter("cart")
        .AddAspNetCoreInstrumentation()
        .AddRuntimeInstrumentation()
        .AddOtlpExporter())
    .WithLogging(l => l
        .AddOtlpExporter());
```

### 9.5 Python — SDK Bootstrap and Span (product-reviews pattern)

```python
# otel_setup.py — shared bootstrap for Python services
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_NAMESPACE
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer, GrpcInstrumentorClient
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
import os

def configure_otel(service_name: str):
    """Bootstrap OTel SDK for a Python service."""
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_NAMESPACE: "astronomy-shop",
        "deployment.environment": os.getenv("DEPLOYMENT_ENV", "development"),
    })

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
        ))
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
        ),
        export_interval_millis=30_000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Auto-instrumentation
    GrpcInstrumentorServer().instrument()
    GrpcInstrumentorClient().instrument()
    Psycopg2Instrumentor().instrument()   # product-reviews only

    return trace.get_tracer(service_name), metrics.get_meter(service_name)


# product_reviews_server.py
from otel_setup import configure_otel

tracer, meter = configure_otel("product_reviews")

reviews_submitted = meter.create_counter(
    "app.reviews.submitted",
    description="Total product reviews submitted",
    unit="{review}",
)

def list_product_reviews(self, request, context):
    with tracer.start_as_current_span("ListProductReviews") as span:
        span.set_attribute("app.product.id", request.product_id)
        span.set_attribute("app.reviews.page", request.page)

        # DB call — auto-instrumented by Psycopg2Instrumentor
        rows = db.query("SELECT * FROM reviews WHERE product_id = %s", (request.product_id,))

        span.set_attribute("app.reviews.count", len(rows))
        return build_response(rows)
```

### 9.6 Ruby — SDK Bootstrap (email pattern)

```ruby
# otel_setup.rb
require 'opentelemetry/sdk'
require 'opentelemetry/exporter/otlp'
require 'opentelemetry/instrumentation/sinatra'
require 'opentelemetry/instrumentation/net/http'

OpenTelemetry::SDK.configure do |c|
  c.service_name = 'email'
  c.resource = OpenTelemetry::SDK::Resources::Resource.create({
    'service.namespace' => 'astronomy-shop',
    'deployment.environment' => ENV.fetch('DEPLOYMENT_ENV', 'development')
  })

  c.add_span_processor(
    OpenTelemetry::SDK::Trace::Export::BatchSpanProcessor.new(
      OpenTelemetry::Exporter::OTLP::Exporter.new(
        endpoint: ENV.fetch('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://otel-collector:4317')
      )
    )
  )

  c.use 'OpenTelemetry::Instrumentation::Sinatra'
  c.use 'OpenTelemetry::Instrumentation::Net::HTTP'
end

TRACER = OpenTelemetry.tracer_provider.tracer('email', '1.0.0')

# email_server.rb — in the /send_order_confirmation route
post '/send_order_confirmation' do
  TRACER.in_span('sendOrderConfirmation') do |span|
    order = JSON.parse(request.body.read)
    # NOTE: Do NOT add email address as span attribute
    span.set_attribute('app.email.template', 'order_confirmation')
    span.set_attribute('app.order.id', order['order']['orderId'])

    # ... render and send email ...

    span.set_attribute('app.email.status', 'sent')
    status 200
  end
end
```

### 9.7 PHP — SDK Bootstrap (quote pattern)

```php
<?php
// otel_bootstrap.php — required at top of each PHP request (or via auto_prepend_file)
use OpenTelemetry\API\Globals;
use OpenTelemetry\SDK\Sdk;
use OpenTelemetry\SDK\Trace\TracerProvider;
use OpenTelemetry\SDK\Trace\SpanProcessor\BatchSpanProcessor;
use OpenTelemetry\Contrib\Otlp\OtlpHttpExporter;
use OpenTelemetry\SDK\Common\Attribute\Attributes;
use OpenTelemetry\SDK\Resource\ResourceInfo;
use OpenTelemetry\SemConv\ResourceAttributes;
use OpenTelemetry\Context\Propagation\TextMapPropagator;
use OpenTelemetry\API\Propagation\TraceContextPropagator;

$resource = ResourceInfo::create(Attributes::create([
    ResourceAttributes::SERVICE_NAME => 'quote',
    ResourceAttributes::SERVICE_NAMESPACE => 'astronomy-shop',
    'deployment.environment' => getenv('DEPLOYMENT_ENV') ?: 'development',
]));

$exporter = OtlpHttpExporter::fromConnectionString(
    getenv('OTEL_EXPORTER_OTLP_ENDPOINT') ?: 'http://otel-collector:4318',
    'traces'
);

$tracerProvider = TracerProvider::builder()
    ->addSpanProcessor(BatchSpanProcessor::builder($exporter)->build())
    ->setResource($resource)
    ->build();

Sdk::builder()
    ->setTracerProvider($tracerProvider)
    ->setPropagator(TraceContextPropagator::getInstance())
    ->setAutoShutdown(true)
    ->buildAndRegisterGlobal();

// quote.php — main handler
$tracer = Globals::tracerProvider()->getTracer('quote');

// Extract W3C TraceContext from incoming request headers (from checkout)
$carrier = getallheaders();
$context = TraceContextPropagator::getInstance()->extract($carrier);

$span = $tracer->spanBuilder('POST /getquote')
    ->setParent($context)
    ->setSpanKind(\OpenTelemetry\API\Trace\SpanKind::KIND_SERVER)
    ->startSpan();

$scope = $span->activate();
try {
    $items = $_POST['items'] ?? [];
    $span->setAttribute('app.quote.items_count', count($items));
    
    $cost = calculateShippingCost($items);
    $span->setAttribute('app.quote.cost_usd', $cost);
    
    echo json_encode(['cost_usd' => $cost]);
} catch (Exception $e) {
    $span->recordException($e);
    $span->setStatus(\OpenTelemetry\API\Trace\StatusCode::STATUS_ERROR, $e->getMessage());
    http_response_code(500);
} finally {
    $scope->detach();
    $span->end();
}
```

### 9.8 Rust — SDK Bootstrap (shipping pattern)

```rust
// otel.rs — bootstrap module
use opentelemetry::global;
use opentelemetry::trace::TracerProvider;
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::{runtime, trace as sdktrace, Resource};
use opentelemetry_semantic_conventions::resource::{SERVICE_NAME, SERVICE_NAMESPACE};
use tracing_opentelemetry::OpenTelemetryLayer;
use tracing_subscriber::{layer::SubscriberExt, Registry};

pub fn init_otel(service_name: &str) -> sdktrace::Tracer {
    let endpoint = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT")
        .unwrap_or_else(|_| "http://otel-collector:4317".to_string());

    let resource = Resource::new(vec![
        opentelemetry::KeyValue::new(SERVICE_NAME, service_name.to_string()),
        opentelemetry::KeyValue::new(SERVICE_NAMESPACE, "astronomy-shop"),
    ]);

    let tracer = opentelemetry_otlp::new_pipeline()
        .tracing()
        .with_exporter(
            opentelemetry_otlp::new_exporter()
                .tonic()
                .with_endpoint(endpoint),
        )
        .with_trace_config(sdktrace::Config::default().with_resource(resource))
        .install_batch(runtime::Tokio)
        .expect("Failed to initialise OTel tracer");

    global::set_tracer_provider(tracer.provider().unwrap());

    let telemetry_layer = OpenTelemetryLayer::new(tracer.clone());
    let subscriber = Registry::default().with(telemetry_layer);
    tracing::subscriber::set_global_default(subscriber)
        .expect("setting default subscriber failed");

    tracer
}

// main.rs — shipping service handler
use tracing::{instrument, info, error};
use opentelemetry::trace::Tracer;

#[instrument(
    name = "ShipOrder",
    fields(
        app.shipping.items_count = items.len(),
        app.shipping.address.country = %address.country,
    )
)]
pub async fn ship_order(address: Address, items: Vec<CartItem>) -> Result<ShipOrderResponse, Error> {
    let tracking_id = generate_tracking_id();
    
    tracing::Span::current().record("app.shipping.tracking.id", &tracking_id.as_str());
    info!(tracking_id = %tracking_id, "Order shipped successfully");

    Ok(ShipOrderResponse { tracking_id })
}
```

### 9.9 Kafka Consumer — Linked Span (accounting C# pattern)

```csharp
// AccountingConsumer.cs
using System.Diagnostics;
using OpenTelemetry;
using OpenTelemetry.Context.Propagation;

public class AccountingConsumer : IHostedService
{
    private static readonly ActivitySource ActivitySource = new("accounting");
    private static readonly TextMapPropagator Propagator = Propagators.DefaultTextMapPropagator;

    public async Task ProcessMessage(ConsumeResult<string, byte[]> result)
    {
        // Extract W3C TraceContext from Kafka message headers
        var parentContext = Propagator.Extract(
            default,
            result.Message.Headers,
            (headers, name) => {
                var header = headers.FirstOrDefault(h => h.Key == name);
                return header != null
                    ? new[] { System.Text.Encoding.UTF8.GetString(header.GetValueBytes()) }
                    : Enumerable.Empty<string>();
            });

        // Create a linked span — NOT a child span — to preserve trace boundary
        using var activity = ActivitySource.StartActivity(
            "orders process",
            ActivityKind.Consumer,
            parentContext: default,  // new root
            links: new[] {
                new ActivityLink(parentContext.ActivityContext)  // link to producer span
            });

        activity?.SetTag("messaging.system", "kafka");
        activity?.SetTag("messaging.destination.name", "orders");
        activity?.SetTag("messaging.operation", "process");
        activity?.SetTag("messaging.consumer.group.name", "accounting-service");

        try
        {
            var order = ParseOrder(result.Message.Value);
            activity?.SetTag("app.order.id", order.OrderId);

            await PersistToLedger(order);
            activity?.SetTag("app.accounting.status", "recorded");
        }
        catch (Exception ex)
        {
            activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
            activity?.RecordException(ex);
            throw;
        }
    }
}
```

### 9.10 C++ — gRPC Server Instrumentation (currency pattern)

```cpp
// otel_setup.cc
#include "opentelemetry/exporters/otlp/otlp_grpc_exporter_factory.h"
#include "opentelemetry/sdk/trace/batch_span_processor_factory.h"
#include "opentelemetry/sdk/trace/tracer_provider_factory.h"
#include "opentelemetry/trace/provider.h"
#include "opentelemetry/sdk/resource/resource.h"

namespace trace_sdk = opentelemetry::sdk::trace;
namespace otlp = opentelemetry::exporter::otlp;
namespace resource = opentelemetry::sdk::resource;

void InitTracer() {
    auto resource_attributes = resource::ResourceAttributes{
        {"service.name", "currency"},
        {"service.namespace", "astronomy-shop"},
    };
    auto res = resource::Resource::Create(resource_attributes);

    otlp::OtlpGrpcExporterOptions opts;
    opts.endpoint = "otel-collector:4317";
    auto exporter = otlp::OtlpGrpcExporterFactory::Create(opts);

    trace_sdk::BatchSpanProcessorOptions bsp_opts;
    auto processor = trace_sdk::BatchSpanProcessorFactory::Create(
        std::move(exporter), bsp_opts);

    auto provider = trace_sdk::TracerProviderFactory::Create(
        std::move(processor), res);

    opentelemetry::trace::Provider::SetTracerProvider(std::move(provider));
}

// currency_service.cc — in Convert RPC handler
// (gRPC server interceptor handles the outer span automatically)
// Add business attributes to the current span:
grpc::Status CurrencyServiceImpl::Convert(
    grpc::ServerContext* context,
    const CurrencyConversionRequest* request,
    Money* response) {

    auto span = opentelemetry::trace::Provider::GetTracerProvider()
        ->GetTracer("currency")
        ->GetCurrentSpan();

    span->SetAttribute("app.currency.from", request->from().currency_code());
    span->SetAttribute("app.currency.to", request->to_code());

    // ... conversion logic ...

    span->SetAttribute("app.currency.rate", conversion_rate);
    return grpc::Status::OK;
}
```

---

*End of OpenTelemetry SDK Instrumentation Plan*

> **Next Steps:**
> 1. SRE team to review SLO → Telemetry mapping (Section 3) and validate SLI expressions against live Prometheus.
> 2. Engineering team to raise Phase 1 instrumentation tickets for all services in the Phase 1 table (Section 6.1).
> 3. Architecture team to approve the shared bootstrap library design (Section 6.2) before Phase 1 begins.
> 4. Security team to review PII guardrails (Section 5.8) and sign off on `lastFourDigits` allowance.
> 5. Platform team to configure OTel Collector `transform/sanitize_spans` processor (Section 5.8) before Phase 1 rollout.