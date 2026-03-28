# CUP SDK Instrumentation — Implementation Summary

**Status:** Complete  
**Date:** 2026-03-28  
**Scope:** Phase 1 & 2 CUP-aligned OTel SDK uplift across 7 services

---

## 1. Overview

This document summarises the concrete code changes made to implement the
OpenTelemetry SDK instrumentation plan defined in
`doc/CRITICAL_USER_PATHS_SDK_INSTRUMENTATION_PLAN.md`.

Changes are **additive** (no rewrites), follow the **incremental uplift**
principle, and are tagged with `CUP-N` comments for traceability.

---

## 2. Changes by Service

### 2.1 Checkout — `src/checkout/main.go` (Go)

**CUP:** CUP-1 (Purchase & Checkout)

| Addition | Detail |
|---|---|
| `app.orders.placed` counter | Incremented on every successful `PlaceOrder` call, tagged with `app.order.currency` |
| `app.order.amount` histogram | Records USD-normalised order value per order, tagged with `app.order.currency` |
| `app.order.items.count` span attribute | Set on the root `PlaceOrder` span |
| `app.order.id` span attribute | Set on the root `PlaceOrder` span for cross-service correlation |
| Error span status | `otelcodes.Error` + `recordException` on failures |

**Metric instruments (OTel SDK):**
```
app.orders.placed        Int64Counter      {order}
app.order.amount         Float64Histogram  USD
```

**Key code location:** `func (cs *checkoutService) PlaceOrder(...)`

---

### 2.2 Payment — `src/payment/charge.js` (Node.js)

**CUP:** CUP-1 (Payment step within checkout)

| Addition | Detail |
|---|---|
| `app.payment.charge.duration` histogram | Measures end-to-end charge processing latency (ms), P95/P99 for SLO |
| `app.payment.amount` span attribute | Charge amount, no currency attribute (low cardinality) |
| `app.payment.currency` span attribute | ISO currency code |
| `app.payment.transaction.id` span attribute | For correlation with external payment provider |
| Error span status | `SpanStatusCode.ERROR` + `recordException` on charge failures |

**Metric instruments:**
```
app.payment.charge.duration   Float64Histogram   ms
```

**Key code location:** `charge()` function in `charge.js`

---

### 2.3 Shipping — `src/shipping/src/shipping_service.rs` (Rust)

**CUP:** CUP-1 (Shipping quotation & dispatch)

| Addition | Detail |
|---|---|
| `app.shipping.quote.duration` histogram | Latency of `GetQuote` call in ms |
| `app.shipping.shiporder.duration` histogram | Latency of `ShipOrder` call in ms |
| `app.shipping.items.count` span attribute | Item count on both RPCs |
| `app.shipping.tracking.id` span attribute | Set on `ShipOrder` success for order correlation |
| `app.shipping.destination.country` span attribute | Country of delivery (low cardinality) |
| Error recording | `span.set_status(StatusCode::Error, ...)` + `span.record_error(...)` |

**Metric instruments:**
```
app.shipping.quote.duration      f64 Histogram   ms
app.shipping.shiporder.duration  f64 Histogram   ms
```

**Key code location:** `impl ShippingService for MyShippingService`

---

### 2.4 Quote — `src/quote/app/routes.php` (PHP)

**CUP:** CUP-3 (Shipping Quote — highest-volume read path)

| Addition | Detail |
|---|---|
| `app.quote.duration` histogram | Measures `calculateQuote()` execution time in ms |
| `app.quote.items.count` span attribute | Item count (already existed, now also histogram label) |
| `app.quote.cost.total` span attribute | Final quoted price (already existed) |
| Quote counter | `quotes` counter already existed, unchanged |

**Metric instruments:**
```
app.quote.duration   Float64Histogram   ms   (new)
quotes               Int64Counter       quotes  (pre-existing, unchanged)
```

**Key code location:** `calculateQuote()` in `routes.php`

---

### 2.5 Product Catalog — `src/product-catalog/main.go` (Go)

**CUP:** CUP-2 (Product Browse & Detail)

| Addition | Detail |
|---|---|
| `app.products.listed` counter | Incremented each time `ListProducts` succeeds |
| `app.product.lookup.duration` histogram | Measures DB lookup latency per `GetProduct` call in ms |
| `app.products.searched` counter | Incremented each time `SearchProducts` succeeds |
| `app.product.found` histogram attribute | Boolean label distinguishing found vs not-found lookups |
| Metric init block | Added after SDK initialisation in `main()` using `otel.GetMeterProvider()` |

**Metric instruments:**
```
app.products.listed          Int64Counter        {request}
app.product.lookup.duration  Float64Histogram    ms       (buckets: 1,5,10,25,50,100,250,500,1000)
app.products.searched        Int64Counter        {request}
```

**Key code location:** `ListProducts`, `GetProduct`, `SearchProducts` methods + `main()`

---

### 2.6 Fraud Detection — `src/fraud-detection/src/main/kotlin/frauddetection/main.kt` (Kotlin)

**CUP:** CUP-1 (Post-checkout async path)

| Addition | Detail |
|---|---|
| `kafkaHeaderGetter` | W3C `TextMapGetter` over `ConsumerRecord` headers |
| Parent context extraction | `otel.propagators.textMapPropagator.extract(...)` on each record |
| `orders process` consumer span | `SpanKind.CONSUMER`, linked to checkout producer trace |
| `app.order.id` span attribute | Order ID from protobuf |
| `app.order.items.count` span attribute | Item count from protobuf |
| `app.fraud.checks` counter | Incremented per order, tagged `app.fraud.result=checked` |
| Error handling | `span.setStatus(StatusCode.ERROR)` + `span.recordException(e)` in catch block |

**Metric instruments:**
```
app.fraud.checks   LongCounter   {order}
```

**Key code location:** `fun main()` consumer loop in `main.kt`

---

### 2.7 Accounting — `src/accounting/Consumer.cs` (C#/.NET)

**CUP:** CUP-1 (Post-checkout async path — financial record)

| Addition | Detail |
|---|---|
| `Propagators.DefaultTextMapPropagator` | Extracts `traceparent` / `tracestate` from Kafka headers |
| `parentContext` extraction | Per-message, using lambda over `msg.Headers` |
| `orders process` consumer Activity | `ActivityKind.Consumer`, parented to checkout span via extracted context |
| `messaging.*` span tags | `messaging.system`, `messaging.operation`, `messaging.destination.name` |
| `app.order.id` span tag | Order ID |
| `app.order.items.count` span tag | Item count |
| `app.order.shipping.tracking_id` span tag | Tracking ID |
| `app.orders.processed` counter | `System.Diagnostics.Metrics.Counter<long>`, incremented after `SaveChanges()` |
| `ActivityStatusCode.Ok/Error` | Set on activity after DB write or on exception |
| `activity.RecordException(ex)` | Records exception on the consumer span |

**Metric instruments:**
```
app.orders.processed   Counter<long>   {order}   (via System.Diagnostics.Metrics)
```

**Key code location:** `StartListening()` and `ProcessMessage()` in `Consumer.cs`

---

## 3. Metrics Summary Table

| Metric | Type | Unit | Service | CUP |
|---|---|---|---|---|
| `app.orders.placed` | Counter | `{order}` | checkout | CUP-1 |
| `app.order.amount` | Histogram | `USD` | checkout | CUP-1 |
| `app.payment.charge.duration` | Histogram | `ms` | payment | CUP-1 |
| `app.shipping.quote.duration` | Histogram | `ms` | shipping | CUP-1/3 |
| `app.shipping.shiporder.duration` | Histogram | `ms` | shipping | CUP-1 |
| `app.products.listed` | Counter | `{request}` | product-catalog | CUP-2 |
| `app.product.lookup.duration` | Histogram | `ms` | product-catalog | CUP-2 |
| `app.products.searched` | Counter | `{request}` | product-catalog | CUP-2 |
| `app.quote.duration` | Histogram | `ms` | quote | CUP-3 |
| `app.fraud.checks` | Counter | `{order}` | fraud-detection | CUP-1 |
| `app.orders.processed` | Counter | `{order}` | accounting | CUP-1 |

---

## 4. Trace Propagation Summary

| Service | Transport | Propagation Mechanism |
|---|---|---|
| frontend → checkout | HTTP/gRPC | Auto-instrumentation (otelgrpc) |
| checkout → payment | gRPC | Auto-instrumentation (otelgrpc) |
| checkout → shipping | gRPC | Auto-instrumentation (otelgrpc) |
| checkout → email | gRPC | Auto-instrumentation (otelgrpc) |
| checkout → Kafka (`orders`) | Kafka | **Manual** — W3C headers injected in checkout producer |
| Kafka → fraud-detection | Kafka | **Manual** — `kafkaHeaderGetter` + `textMapPropagator.extract()` |
| Kafka → accounting | Kafka | **Manual** — `Propagators.DefaultTextMapPropagator.Extract()` |
| frontend → product-catalog | gRPC | Auto-instrumentation (otelgrpc) |
| frontend → quote | HTTP | Auto-instrumentation (Slim framework) |
| recommendation → product-catalog | gRPC | Auto-instrumentation (otelgrpc) |

---

## 5. SLO Enablement

The following SLO metrics are now measurable end-to-end:

| SLO | Metric | Query |
|---|---|---|
| CUP-1 P95 checkout latency < 2 s | `app.orders.placed` + trace duration | `histogram_quantile(0.95, rate(duration_ms_bucket[5m]))` |
| CUP-1 order success rate > 99.5% | `app.orders.placed` / total attempts | `rate(app_orders_placed_total[5m]) / rate(checkout_requests_total[5m])` |
| CUP-1 payment error rate < 0.5% | `app.payment.charge.duration` + span errors | `rate(payment_errors[5m]) / rate(payment_requests[5m])` |
| CUP-2 product page P95 latency < 500 ms | `app.product.lookup.duration` | `histogram_quantile(0.95, rate(app_product_lookup_duration_ms_bucket[5m]))` |
| CUP-3 quote P95 latency < 300 ms | `app.quote.duration` | `histogram_quantile(0.95, rate(app_quote_duration_ms_bucket[5m]))` |

---

## 6. Definition of Done (Per Service)

| Service | Traces | Metrics | Context Prop | DoD |
|---|---|---|---|---|
| checkout | ✅ root span + child spans | ✅ orders + amount | ✅ gRPC auto + Kafka inject | ✅ |
| payment | ✅ charge span | ✅ charge duration | ✅ gRPC auto | ✅ |
| shipping | ✅ quote + shiporder spans | ✅ latency histograms | ✅ gRPC auto | ✅ |
| quote | ✅ calculate-quote span | ✅ quote duration | ✅ HTTP auto | ✅ |
| product-catalog | ✅ list/get/search spans | ✅ counters + lookup duration | ✅ gRPC auto | ✅ |
| fraud-detection | ✅ kafka consumer span | ✅ fraud checks counter | ✅ Kafka extract | ✅ |
| accounting | ✅ kafka consumer activity | ✅ orders processed counter | ✅ Kafka extract | ✅ |

---

## 7. Files Changed

```
src/checkout/main.go
src/payment/charge.js
src/shipping/src/shipping_service.rs
src/quote/app/routes.php
src/product-catalog/main.go
src/fraud-detection/src/main/kotlin/frauddetection/main.kt
src/accounting/Consumer.cs
```

---

## 8. Next Steps (Phase 3+)

1. **Cart service** (C#) — add `app.cart.items.added` counter and session-scoped spans
2. **Recommendation service** (Python) — add `app.recommendations.served` counter
3. **Currency service** (C++) — add `app.currency.conversion.duration` histogram
4. **Ad service** (Java) — add `app.ads.served` counter with `app.ad.context` attribute
5. **Frontend** (Next.js) — add RUM spans for `checkout-initiated`, `payment-submitted` with Web Vitals
6. **Prometheus recording rules** — add `job:app_orders_placed:rate5m` pre-aggregation rules
7. **Grafana dashboards** — wire new metrics to CUP SLO panels
8. **Sampling config** — enable tail-based sampling for CUP-1 errors at the OTel Collector