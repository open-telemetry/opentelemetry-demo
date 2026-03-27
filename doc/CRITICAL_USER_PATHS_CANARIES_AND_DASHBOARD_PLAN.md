# Canaries & Grafana Dashboard Implementation Plan

> **Role:** Principal SRE & Observability Architect  
> **Source:** `doc/CRITICAL_USER_PATHS_ANALYSIS.md`, `doc/CRITICAL_USER_PATHS_SLO.md`, `doc/application-overview.md`  
> **Date:** March 2026

---

## Table of Contents

1. [SLO Summary (Reference)](#part-1-slo-summary)
2. [OTel Instrumentation Strategy](#part-2-otel-instrumentation-strategy)
3. [Grafana Synthetic Monitoring Canaries](#part-3-grafana-synthetic-monitoring-canaries)
4. [Grafana Dashboard Architecture](#part-4-grafana-dashboard-architecture)

---

## Part 1: SLO Summary

> Full SLO definitions are in `doc/CRITICAL_USER_PATHS_SLO.md`. This section is a quick reference for dashboard thresholds.

| CUP | Availability | P95 Latency | Error Budget (28d) |
|---|---|---|---|
| 1 — Checkout & Payment | 99.95% | 3,000 ms | 21.6 min |
| 2 — Product Browse & Discovery | 99.9% | 800 ms | 43.2 min |
| 3 — Shopping Cart Management | 99.95% | 300 ms | 21.6 min |
| 4 — Order Fulfillment (ShipOrder) | 99.9% | 800 ms | 43.2 min |
| 4 — Order Fulfillment (Async) | 99.5% | 30 s lag | 3.6 hr |
| 5 — Shipping Quote | 99.9% | 600 ms | 43.2 min |
| 6 — Currency Selection | 99.95% | 100 ms | 21.6 min |
| 7 — AI Product Assistant | 99.0% | 10,000 ms | 7.2 hr |
| 8 — Product Reviews | 99.5% | 500 ms | 3.6 hr |

---

## Part 2: OTel Instrumentation Strategy

### 2.1 Overview

The Astronomy Shop ships with OpenTelemetry auto-instrumentation on all services and exports via OTLP to the `otel-collector`, which fans out to Prometheus (metrics), Tempo (traces), and Loki (logs). The strategy below focuses on **closing observability gaps** — specifically Kafka async trace context propagation and `cup.name` attribute tagging for CUP-scoped filtering in Grafana Explore and dashboard variables.

### 2.2 OTel Collector Configuration for Grafana Stack

```yaml
# src/otel-collector/otelcol-config-extras.yml
exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
    default_labels_enabled:
      exporter: false
      job: true
    resource_to_telemetry_conversion:
      enabled: true

processors:
  attributes/cup_index:
    actions:
      - key: cup.name
        action: upsert
        from_attribute: cup.name   # must be set by application spans
  resource/service_meta:
    attributes:
      - key: deployment.environment
        value: production
        action: upsert

service:
  pipelines:
    traces:
      processors: [memory_limiter, batch, attributes/cup_index]
      exporters: [otlp/tempo, debug]
    metrics:
      exporters: [prometheus]
    logs:
      exporters: [loki]
```

### 2.3 Tracing Async Patterns (Kafka)

The checkout → Kafka → accounting/fraud-detection flow breaks the trace context because Kafka is message-based. Context must be propagated through **Kafka message headers** using the W3C TraceContext format to link producer and consumer spans in Tempo.

#### Producer Side — Checkout Service (Go)

```go
// src/checkout/kafka/producer.go
func publishOrderEvent(ctx context.Context, order *pb.OrderResult) error {
    tracer := otel.Tracer("checkout")
    ctx, span := tracer.Start(ctx, "kafka.produce orders",
        trace.WithSpanKind(trace.SpanKindProducer),
        trace.WithAttributes(
            attribute.String("messaging.system", "kafka"),
            attribute.String("messaging.destination", "orders"),
            attribute.String("messaging.operation", "publish"),
            attribute.String("cup.name", "checkout_payment"),
            attribute.String("order.id", order.OrderId),
        ),
    )
    defer span.End()

    headers := []kafka.Header{}
    otel.GetTextMapPropagator().Inject(ctx, kafkaHeaderCarrier{headers: &headers})

    return producer.Produce(&kafka.Message{
        TopicPartition: kafka.TopicPartition{Topic: &ordersTopicName, Partition: kafka.PartitionAny},
        Value:          eventBytes,
        Headers:        headers,
    }, nil)
}
```

#### Consumer Side — Accounting Service (C#)

```csharp
// src/accounting/Consumer.cs
public async Task ConsumeAsync(ConsumeResult<string, byte[]> result)
{
    var parentContext = Propagators.DefaultTextMapPropagator.Extract(
        default,
        result.Message.Headers,
        (headers, key) => headers
            .Where(h => h.Key == key)
            .Select(h => Encoding.UTF8.GetString(h.GetValueBytes()))
            .ToList()
    );

    using var activity = ActivitySource.StartActivity(
        "kafka.consume orders",
        ActivityKind.Consumer,
        parentContext.ActivityContext,
        tags: new[]
        {
            new KeyValuePair<string, object?>("messaging.system", "kafka"),
            new KeyValuePair<string, object?>("messaging.destination", "orders"),
            new KeyValuePair<string, object?>("cup.name", "order_fulfillment"),
        }
    );
    await ProcessOrderEvent(result.Message.Value);
}
```

#### Consumer Side — Fraud Detection (Kotlin)

```kotlin
// src/fraud-detection/src/main/kotlin/Consumer.kt
val parentContext = GlobalOpenTelemetry.getPropagators().textMapPropagator.extract(
    Context.current(),
    record.headers(),
    object : TextMapGetter<Headers> {
        override fun keys(carrier: Headers) = carrier.map { it.key() }
        override fun get(carrier: Headers?, key: String) =
            carrier?.lastHeader(key)?.value()?.let { String(it) }
    }
)

val span = tracer.spanBuilder("kafka.consume orders")
    .setParent(parentContext)
    .setSpanKind(SpanKind.CONSUMER)
    .setAttribute("messaging.system", "kafka")
    .setAttribute("cup.name", "order_fulfillment")
    .startSpan()
```

### 2.4 Custom Attribute Tagging Strategy

Every span on a CUP path **must carry `cup.name`** to enable filtering in Grafana Explore (Tempo TraceQL) and to power the `cup_name` dashboard variable.

#### Required Custom Attributes

| Attribute | Type | Values | Applied To |
|---|---|---|---|
| `cup.name` | string | `checkout_payment`, `browse_discovery`, `cart_management`, `order_fulfillment`, `shipping_quote`, `currency_display`, `ai_assistant`, `product_reviews` | All spans on CUP paths |
| `cup.step` | string | e.g., `place_order`, `charge_payment`, `get_cart` | Key orchestration spans |
| `user.session_id` | string | session UUID | Frontend BFF spans |
| `order.id` | string | UUID | Checkout, payment, shipping, email spans |
| `product.id` | string | product UUID | Browse, reviews, AI assistant spans |
| `payment.card_last_four` | string | last 4 digits only | Payment spans — **never full PAN or CVV** |
| `feature_flag.name` | string | flag ID | Any span gated by FlagD |
| `feature_flag.evaluated_value` | string | resolved flag value | Any span gated by FlagD |

#### Example — Frontend BFF Checkout Span (TypeScript)

```typescript
// src/frontend/pages/api/checkout.ts
const span = tracer.startSpan('POST /api/checkout', {
  attributes: {
    'http.method': 'POST',
    'http.route': '/api/checkout',
    'cup.name': 'checkout_payment',
    'cup.step': 'bff_checkout',
    'user.session_id': req.cookies['session-id'] ?? 'unknown',
  },
});
try {
  await context.with(trace.setSpan(context.active(), span), async () => {
    const result = await checkoutClient.placeOrder(buildRequest(req.body));
    span.setAttribute('order.id', result.order.orderId);
    res.status(200).json(result);
  });
} catch (err) {
  span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
  span.recordException(err);
  res.status(500).json({ error: err.message });
} finally {
  span.end();
}
```

#### Example — Payment Span — Sensitive Data Handling (Node.js)

```javascript
// src/payment/charge.js — NEVER log PAN or CVV in span attributes
const span = tracer.startSpan('PaymentService/Charge', {
  attributes: {
    'cup.name': 'checkout_payment',
    'cup.step': 'payment_charge',
    'payment.currency': charge.amount.currencyCode,
    'payment.card_last_four': charge.creditCard.creditCardNumber.slice(-4),
    // ❌ 'payment.card_number': ...  — FORBIDDEN
    // ❌ 'payment.cvv': ...          — FORBIDDEN
  },
});
```

### 2.5 Instrumentation Coverage Matrix

| Service | Language | Auto-Instrumented | Manual Spans Needed | Kafka Context |
|---|---|---|---|---|
| frontend | Node.js/TS | ✅ HTTP, gRPC | `cup.name`, `user.session_id` | N/A |
| checkout | Go | ✅ HTTP, gRPC | `cup.name`, `order.id` | ✅ Producer |
| cart | C# | ✅ gRPC | `cup.name` | N/A |
| payment | Node.js | ✅ gRPC | `cup.name`, `payment.card_last_four` | N/A |
| currency | C++ | ⚠️ Manual only | All spans manual | N/A |
| shipping | Rust | ✅ gRPC | `cup.name` | N/A |
| email | Ruby | ✅ HTTP | `cup.name`, `order.id` | N/A |
| product-catalog | Go | ✅ gRPC | `cup.name`, `product.id` | N/A |
| recommendation | Python | ✅ gRPC | `cup.name` | N/A |
| ad | Java | ✅ gRPC | `cup.name` | N/A |
| product-reviews | Python | ✅ gRPC | `cup.name`, `product.id` | N/A |
| quote | PHP | ⚠️ Manual | All spans manual | N/A |
| llm | Python | ✅ HTTP | `cup.name`, `llm.model`, `llm.usage.total_tokens` | N/A |
| accounting | C# | ✅ Kafka | `cup.name` | ✅ Consumer |
| fraud-detection | Kotlin | ✅ Kafka | `cup.name` | ✅ Consumer |

---

## Part 3: Grafana Synthetic Monitoring Canaries

### 3.1 Technology Stack

Grafana Synthetic Monitoring uses **k6** as its scripting engine. Two check types are used:

- **HTTP check** (heartbeat): Simple probe against a single URL. Configured declaratively.
- **Browser check** (workflow): k6 browser module (Playwright-compatible API) for multi-step UI flows.
- **Scripted k6 check** (API workflow): k6 HTTP API for multi-step API flows without a UI.

All synthetic results are stored as Prometheus metrics in Grafana Cloud and queried using PromQL in dashboards.

### 3.2 Canary Type Selection

| CUP | Canary Type | Script Type | Rationale |
|---|---|---|---|
| 1 — Checkout & Payment | **Workflow** | k6 Browser | Full 6-step UI transaction; must exercise real purchase path |
| 2 — Product Browse & Discovery | **Workflow** | k6 Browser | Multi-step: homepage → list → detail → recommendations |
| 3 — Shopping Cart Management | **Workflow** | k6 Scripted HTTP | State transitions (add → verify → empty) via API |
| 4 — Order Fulfillment (Async) | **Heartbeat** | HTTP probe | Kafka consumers untestable synthetically; probe ShipOrder BFF endpoint |
| 5 — Shipping Quote | **Heartbeat** | HTTP probe | Single endpoint; no UI or state required |
| 6 — Currency Selection | **Heartbeat** | HTTP probe | Single gRPC-backed GET; trivial response validation |
| 7 — AI Product Assistant | **Workflow** | k6 Scripted HTTP | Two-step: GET product → POST question → validate non-empty answer |
| 8 — Product Reviews | **Workflow** | k6 Scripted HTTP | Two-step: GET reviews list → GET average score |

### 3.3 CUP 1 — Checkout & Payment (k6 Browser Workflow)

```javascript
// canaries/cup1-checkout-payment.js
import { browser } from 'k6/browser';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    checkout_workflow: {
      executor: 'constant-vus',
      vus: 1,
      duration: '1m',
      options: { browser: { type: 'chromium' } },
    },
  },
  thresholds: {
    browser_web_vital_lcp: ['p95 < 3000'],
    checks: ['rate > 0.95'],
  },
};

const BASE_URL = __ENV.APP_BASE_URL || 'http://localhost:8080';

export default async function () {
  const page = await browser.newPage();

  try {
    // Step 1: Load homepage
    await page.goto(`${BASE_URL}/`);
    await page.waitForSelector('[data-testid="product-list"]');
    check(page, { 'Homepage: product list visible': p =>
      p.locator('[data-testid="product-card"]').count() > 0
    });

    // Step 2: Open first product
    await page.locator('[data-testid="product-card"] a').first().click();
    await page.waitForSelector('[data-testid="add-to-cart-btn"]');
    check(page, { 'Product page: add-to-cart visible': p =>
      p.locator('[data-testid="add-to-cart-btn"]').isVisible()
    });

    // Step 3: Add to cart
    await page.locator('[data-testid="add-to-cart-btn"]').click();
    await page.waitForSelector('[data-testid="cart-item-count"]');
    const cartCount = await page.locator('[data-testid="cart-item-count"]').textContent();
    check(null, { 'Cart: item count > 0': () => parseInt(cartCount, 10) > 0 });

    // Step 4: Navigate to cart
    await page.goto(`${BASE_URL}/cart`);
    await page.waitForSelector('[data-testid="cart-item"]');
    check(page, { 'Cart page: item visible': p =>
      p.locator('[data-testid="cart-item"]').count() > 0
    });

    // Step 5: Fill checkout form
    await page.locator('[data-testid="checkout-btn"]').click();
    await page.waitForSelector('[data-testid="checkout-form"]');

    await page.locator('[name="email"]').type('canary-test@example.com');
    await page.locator('[name="street_address"]').type('123 Test Street');
    await page.locator('[name="city"]').type('Sydney');
    await page.locator('[name="state"]').type('NSW');
    await page.locator('[name="country"]').type('AU');
    await page.locator('[name="zip_code"]').type('2000');
    await page.locator('[name="credit_card_number"]').type('4432801561520454');
    await page.locator('[name="credit_card_expiration_month"]').type('01');
    await page.locator('[name="credit_card_expiration_year"]').type('2030');
    await page.locator('[name="credit_card_cvv"]').type('672');

    // Step 6: Place order and verify confirmation
    await page.locator('[data-testid="place-order-btn"]').click();
    await page.waitForSelector('[data-testid="order-confirmation"]', { timeout: 30000 });

    const orderId = await page.locator('[data-testid="order-id"]').textContent();
    check(null, {
      'Order placed: confirmation visible': () => true,
      'Order placed: order ID non-empty': () => orderId && orderId.trim().length >= 8,
    });

  } finally {
    await page.close();
  }

  sleep(1);
}
```

### 3.4 CUP 2 — Product Browse & Discovery (k6 Browser Workflow)

```javascript
// canaries/cup2-browse-discovery.js
import { browser } from 'k6/browser';
import { check } from 'k6';

export const options = {
  scenarios: {
    browse_workflow: {
      executor: 'constant-vus',
      vus: 1,
      duration: '1m',
      options: { browser: { type: 'chromium' } },
    },
  },
  thresholds: {
    checks: ['rate > 0.99'],
  },
};

const BASE_URL = __ENV.APP_BASE_URL || 'http://localhost:8080';

export default async function () {
  const page = await browser.newPage();

  try {
    // Step 1: Storefront loads with products
    const response = await page.goto(`${BASE_URL}/`);
    check(response, { 'Storefront: HTTP 200': r => r.status() === 200 });
    await page.waitForSelector('[data-testid="product-list"]');
    const productCount = await page.locator('[data-testid="product-card"]').count();
    check(null, { 'Storefront: ≥1 product visible': () => productCount >= 1 });

    // Step 2: /api/products returns valid array
    const apiResult = await page.evaluate(async (base) => {
      const res = await fetch(`${base}/api/products`);
      const body = await res.json();
      return { status: res.status, count: Array.isArray(body) ? body.length : -1 };
    }, BASE_URL);
    check(apiResult, {
      '/api/products: HTTP 200': r => r.status === 200,
      '/api/products: returns array': r => r.count > 0,
    });

    // Step 3: Product detail page loads
    await page.locator('[data-testid="product-card"] a').first().click();
    await page.waitForSelector('[data-testid="product-title"]');
    const title = await page.locator('[data-testid="product-title"]').textContent();
    check(null, { 'Product detail: title non-empty': () => title && title.trim().length > 0 });

    // Step 4: Recommendations render
    await page.waitForSelector('[data-testid="recommendation-list"]', { timeout: 8000 });
    check(page, { 'Recommendations: section visible': p =>
      p.locator('[data-testid="recommendation-list"]').isVisible()
    });

  } finally {
    await page.close();
  }
}
```

### 3.5 CUP 3 — Shopping Cart Management (k6 Scripted HTTP Workflow)

```javascript
// canaries/cup3-cart-management.js
import http from 'k6/http';
import { check, group } from 'k6';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    'http_req_duration{scenario:cart_add}': ['p95 < 300'],
    checks: ['rate == 1.0'],
  },
};

const BASE_URL = __ENV.APP_BASE_URL || 'http://localhost:8080';
const HEADERS = { 'Content-Type': 'application/json' };

export default function () {
  // Step 1: Add item to cart
  group('AddItemToCart', () => {
    const res = http.post(
      `${BASE_URL}/api/cart`,
      JSON.stringify({ productId: '66VCHSJNUP', quantity: 1 }),
      { headers: HEADERS, tags: { scenario: 'cart_add' } }
    );
    check(res, {
      'AddItem: status 200': r => r.status === 200,
    });
  });

  // Step 2: Read cart and verify item present
  group('ReadCart', () => {
    const res = http.get(`${BASE_URL}/api/cart`);
    const body = res.json();
    check(res, {
      'GetCart: status 200': r => r.status === 200,
    });
    check(body, {
      'GetCart: items array non-empty': b => Array.isArray(b.items) && b.items.length > 0,
    });
  });

  // Step 3: Empty cart and verify cleared
  group('EmptyCart', () => {
    const del = http.del(`${BASE_URL}/api/cart`);
    check(del, { 'EmptyCart: status 200': r => r.status === 200 });

    const verify = http.get(`${BASE_URL}/api/cart`);
    const body = verify.json();
    check(body, {
      'EmptyCart: items empty after delete': b =>
        !b.items || b.items.length === 0,
    });
  });
}
```

### 3.6 CUP 5 — Shipping Quote (HTTP Heartbeat)

```javascript
// canaries/cup5-shipping-quote.js
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_duration: ['p95 < 600'],
    checks: ['rate == 1.0'],
  },
};

const BASE_URL = __ENV.APP_BASE_URL || 'http://localhost:8080';

export default function () {
  const params = new URLSearchParams({
    'items[0][productId]': '66VCHSJNUP',
    'items[0][quantity]': '1',
    currencyCode: 'USD',
    'address[streetAddress]': '123 Test St',
    'address[city]': 'Sydney',
    'address[state]': 'NSW',
    'address[country]': 'AU',
    'address[zipCode]': '2000',
  });

  const res = http.get(`${BASE_URL}/api/shipping?${params}`);
  const body = res.json();

  check(res, { 'ShippingQuote: HTTP 200': r => r.status === 200 });
  check(body, {
    'ShippingQuote: cost field present': b => b.shipping && b.shipping.cost !== undefined,
  });
}
```

### 3.7 CUP 6 — Currency Selection (HTTP Heartbeat)

```javascript
// canaries/cup6-currency.js
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_duration: ['p95 < 100'],
    checks: ['rate == 1.0'],
  },
};

const BASE_URL = __ENV.APP_BASE_URL || 'http://localhost:8080';

export default function () {
  const res = http.get(`${BASE_URL}/api/currency`);
  const body = res.json();

  check(res, { 'Currency: HTTP 200': r => r.status === 200 });
  check(body, {
    'Currency: returns array': b => Array.isArray(b),
    'Currency: ≥5 entries': b => Array.isArray(b) && b.length >= 5,
    'Currency: USD present': b => Array.isArray(b) && b.includes('USD'),
  });
}
```

### 3.8 CUP 7 — AI Product Assistant (k6 Scripted HTTP Workflow)

```javascript
// canaries/cup7-ai-assistant.js
import http from 'k6/http';
import { check, group, sleep } from 'k6';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    'http_req_duration{step:ai_question}': ['p95 < 10000'],
    checks: ['rate == 1.0'],
  },
};

const BASE_URL = __ENV.APP_BASE_URL || 'http://localhost:8080';
const PRODUCT_ID = '66VCHSJNUP';
const HEADERS = { 'Content-Type': 'application/json' };

export default function () {
  // Step 1: Verify product endpoint
  group('LoadProduct', () => {
    const res = http.get(`${BASE_URL}/api/products/${PRODUCT_ID}`);
    const body = res.json();
    check(res, { 'GetProduct: HTTP 200': r => r.status === 200 });
    check(body, { 'GetProduct: name non-empty': b => b.name && b.name.length > 0 });
  });

  // Step 2: Ask AI question (slow — LLM inference)
  group('AskAIAssistant', () => {
    const res = http.post(
      `${BASE_URL}/api/product-ask-ai-assistant/${PRODUCT_ID}`,
      JSON.stringify({ question: 'What are the key features of this product?' }),
      { headers: HEADERS, timeout: '25s', tags: { step: 'ai_question' } }
    );
    const body = res.json();
    check(res, { 'AI Assistant: HTTP 200': r => r.status === 200 });
    check(body, {
      'AI Assistant: answer non-empty': b => b.answer && b.answer.length >= 20,
    });
  });
}
```

### 3.9 CUP 8 — Product Reviews (k6 Scripted HTTP Workflow)

```javascript
// canaries/cup8-product-reviews.js
import http from 'k6/http';
import { check, group } from 'k6';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_duration: ['p95 < 500'],
    checks: ['rate == 1.0'],
  },
};

const BASE_URL = __ENV.APP_BASE_URL || 'http://localhost:8080';
const PRODUCT_ID = '66VCHSJNUP';

export default function () {
  // Step 1: Get reviews list
  group('GetReviews', () => {
    const res = http.get(`${BASE_URL}/api/product-reviews/${PRODUCT_ID}`);
    const body = res.json();
    check(res, { 'GetReviews: HTTP 200': r => r.status === 200 });
    check(body, { 'GetReviews: reviews field present': b => 'reviews' in b });
  });

  // Step 2: Get average score
  group('GetAvgScore', () => {
    const res = http.get(`${BASE_URL}/api/product-reviews-avg-score/${PRODUCT_ID}`);
    const body = res.json();
    check(res, { 'GetAvgScore: HTTP 200': r => r.status === 200 });
    check(body, {
      'GetAvgScore: score is number': b => typeof b.score === 'number',
    });
  });
}
```

### 3.10 Grafana Synthetic Monitoring Configuration (YAML)

Canaries are registered in Grafana Synthetic Monitoring via the `grafana-synthetic-monitoring` provisioning API or Terraform provider.

```yaml
# provisioning/synthetic-monitoring/checks.yaml

- job: cup1-checkout-payment
  target: "http://astronomy-shop.internal:8080"
  frequency: 300000     # every 5 minutes (ms)
  timeout: 60000
  type: scripted
  settings:
    scripted:
      script: "canaries/cup1-checkout-payment.js"
  labels:
    cup: "1"
    cup_name: "checkout_payment"
    canary_type: "workflow"
  alert_sensitivity: high

- job: cup2-browse-discovery
  target: "http://astronomy-shop.internal:8080"
  frequency: 300000
  timeout: 60000
  type: scripted
  settings:
    scripted:
      script: "canaries/cup2-browse-discovery.js"
  labels:
    cup: "2"
    cup_name: "browse_discovery"
    canary_type: "workflow"
  alert_sensitivity: high

- job: cup3-cart-management
  target: "http://astronomy-shop.internal:8080"
  frequency: 300000
  timeout: 30000
  type: scripted
  settings:
    scripted:
      script: "canaries/cup3-cart-management.js"
  labels:
    cup: "3"
    cup_name: "cart_management"
    canary_type: "workflow"
  alert_sensitivity: high

- job: cup5-shipping-quote
  target: "http://astronomy-shop.internal:8080/api/shipping"
  frequency: 300000
  timeout: 20000
  type: http
  settings:
    http:
      method: GET
      valid_status_codes: [200]
      fail_if_body_not_matches_regexp: '"cost"'
  labels:
    cup: "5"
    cup_name: "shipping_quote"
    canary_type: "heartbeat"

- job: cup6-currency
  target: "http://astronomy-shop.internal:8080/api/currency"
  frequency: 300000
  timeout: 10000
  type: http
  settings:
    http:
      method: GET
      valid_status_codes: [200]
      fail_if_body_not_matches_regexp: '"USD"'
  labels:
    cup: "6"
    cup_name: "currency_display"
    canary_type: "heartbeat"

- job: cup7-ai-assistant
  target: "http://astronomy-shop.internal:8080"
  frequency: 600000     # every 10 minutes
  timeout: 120000
  type: scripted
  settings:
    scripted:
      script: "canaries/cup7-ai-assistant.js"
  labels:
    cup: "7"
    cup_name: "ai_assistant"
    canary_type: "workflow"
  alert_sensitivity: low

- job: cup8-product-reviews
  target: "http://astronomy-shop.internal:8080"
  frequency: 300000
  timeout: 30000
  type: scripted
  settings:
    scripted:
      script: "canaries/cup8-product-reviews.js"
  labels:
    cup: "8"
    cup_name: "product_reviews"
    canary_type: "workflow"
  alert_sensitivity: low
```

---

## Part 4: Grafana Dashboard Architecture

### 4.1 Dashboard Overview

Three Grafana dashboards form the Mission Control observability suite. All use the `prometheus` data source for metrics and `tempo` for traces.

| Dashboard UID | Title | Primary Audience |
|---|---|---|
| `cup-executive` | 🔭 Astronomy Shop — Executive SLO View | Leadership, on-call |
| `cup-performance` | Astronomy Shop — CUP Performance (P95/P99) | SRE, engineers |
| `cup-reliability` | Astronomy Shop — Reliability (Canary vs Real-User) | SRE on-call |

All dashboards share these **template variables**:

```json
{
  "templating": {
    "list": [
      {
        "name": "environment",
        "type": "custom",
        "options": [
          {"text": "production", "value": "production"},
          {"text": "staging", "value": "staging"}
        ],
        "current": {"text": "production", "value": "production"}
      },
      {
        "name": "cup_name",
        "type": "custom",
        "options": [
          {"text": "All", "value": ".*"},
          {"text": "Checkout", "value": "checkout_payment"},
          {"text": "Browse", "value": "browse_discovery"},
          {"text": "Cart", "value": "cart_management"},
          {"text": "Fulfillment", "value": "order_fulfillment"},
          {"text": "AI Assistant", "value": "ai_assistant"}
        ]
      }
    ]
  }
}
```

### 4.2 Executive View Dashboard (`cup-executive`)

Each CUP is represented by a **Stat panel** showing current availability (green ≥ target, red < target) backed by a PromQL availability query.

```json
{
  "uid": "cup-executive",
  "title": "🔭 Astronomy Shop — Executive SLO View",
  "refresh": "1m",
  "time": {"from": "now-1h", "to": "now"},
  "panels": [
    {
      "id": 1,
      "type": "text",
      "title": "",
      "gridPos": {"x": 0, "y": 0, "w": 24, "h": 2},
      "options": {
        "mode": "markdown",
        "content": "# Mission Control — 8 Critical User Paths\nGreen = SLO met. Red = SLO breached or error budget burning."
      }
    },
    {
      "id": 2,
      "type": "stat",
      "title": "CUP 1 — Checkout & Payment (SLO: 99.95%)",
      "gridPos": {"x": 0, "y": 2, "w": 12, "h": 4},
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "red", "value": null},
              {"color": "yellow", "value": 0.9990},
              {"color": "green", "value": 0.9995}
            ]
          },
          "mappings": []
        }
      },
      "targets": [
        {
          "datasource": {"type": "prometheus"},
          "expr": "sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/checkout\",http_response_status_code!~\"5..\"}[5m])) / sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/checkout\"}[5m]))",
          "legendFormat": "Availability"
        }
      ],
      "options": {
        "reduceOptions": {"calcs": ["lastNotNull"]},
        "orientation": "auto",
        "colorMode": "background",
        "graphMode": "none"
      }
    },
    {
      "id": 3,
      "type": "stat",
      "title": "CUP 2 — Product Browse (SLO: 99.9%)",
      "gridPos": {"x": 12, "y": 2, "w": 6, "h": 4},
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "red", "value": null},
              {"color": "yellow", "value": 0.9985},
              {"color": "green", "value": 0.9990}
            ]
          }
        }
      },
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/products\",http_response_status_code!~\"5..\"}[5m])) / sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/products\"}[5m]))",
        "legendFormat": "Availability"
      }]
    },
    {
      "id": 4,
      "type": "stat",
      "title": "CUP 3 — Cart Management (SLO: 99.95%)",
      "gridPos": {"x": 18, "y": 2, "w": 6, "h": 4},
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "red", "value": null},
              {"color": "green", "value": 0.9995}
            ]
          }
        }
      },
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/cart\",http_response_status_code!~\"5..\"}[5m])) / sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/cart\"}[5m]))",
        "legendFormat": "Availability"
      }]
    },
    {
      "id": 5,
      "type": "stat",
      "title": "CUP 4 — Order Fulfillment (SLO: 99.9%)",
      "gridPos": {"x": 0, "y": 6, "w": 6, "h": 3},
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "sum(rate(rpc_server_duration_count{rpc_service=\"hipstershop.ShippingService\",rpc_method=\"ShipOrder\",rpc_grpc_status_code=\"0\"}[5m])) / sum(rate(rpc_server_duration_count{rpc_service=\"hipstershop.ShippingService\",rpc_method=\"ShipOrder\"}[5m]))"
      }],
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {"steps": [{"color": "red","value": null},{"color": "green","value": 0.9990}]}
        }
      }
    },
    {
      "id": 6,
      "type": "stat",
      "title": "CUP 5 — Shipping Quote (SLO: 99.9%)",
      "gridPos": {"x": 6, "y": 6, "w": 6, "h": 3},
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "sum(rate(http_server_request_duration_seconds_count{http_route=\"/getquote\",http_response_status_code!~\"5..\"}[5m])) / sum(rate(http_server_request_duration_seconds_count{http_route=\"/getquote\"}[5m]))"
      }],
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {"steps": [{"color": "red","value": null},{"color": "green","value": 0.9990}]}
        }
      }
    },
    {
      "id": 7,
      "type": "stat",
      "title": "CUP 6 — Currency (SLO: 99.95%)",
      "gridPos": {"x": 12, "y": 6, "w": 6, "h": 3},
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "sum(rate(rpc_server_duration_count{rpc_service=\"hipstershop.CurrencyService\",rpc_grpc_status_code=\"0\"}[5m])) / sum(rate(rpc_server_duration_count{rpc_service=\"hipstershop.CurrencyService\"}[5m]))"
      }],
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {"steps": [{"color": "red","value": null},{"color": "green","value": 0.9995}]}
        }
      }
    },
    {
      "id": 8,
      "type": "stat",
      "title": "CUP 7 — AI Assistant (SLO: 99.0%)",
      "gridPos": {"x": 18, "y": 6, "w": 6, "h": 3},
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "sum(rate(http_server_request_duration_seconds_count{http_route=\"/v1/chat/completions\",http_response_status_code!~\"5..\"}[5m])) / sum(rate(http_server_request_duration_seconds_count{http_route=\"/v1/chat/completions\"}[5m]))"
      }],
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {"steps": [{"color": "red","value": null},{"color": "green","value": 0.9900}]}
        }
      }
    },
    {
      "id": 9,
      "type": "stat",
      "title": "CUP 8 — Product Reviews (SLO: 99.5%)",
      "gridPos": {"x": 0, "y": 9, "w": 6, "h": 3},
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "sum(rate(rpc_server_duration_count{rpc_service=\"oteldemo.ProductReviewService\",rpc_grpc_status_code=\"0\"}[5m])) / sum(rate(rpc_server_duration_count{rpc_service=\"oteldemo.ProductReviewService\"}[5m]))"
      }],
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {"steps": [{"color": "red","value": null},{"color": "green","value": 0.9950}]}
        }
      }
    },
    {
      "id": 10,
      "type": "gauge",
      "title": "CUP 1 — Error Budget Remaining (28d)",
      "description": "Percentage of monthly error budget not yet consumed. Alert at <50%.",
      "gridPos": {"x": 6, "y": 9, "w": 18, "h": 3},
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "max": 100,
          "thresholds": {
            "steps": [
              {"color": "red", "value": 0},
              {"color": "yellow", "value": 25},
              {"color": "green", "value": 50}
            ]
          }
        }
      },
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "100 * (1 - (sum(increase(http_server_request_duration_seconds_count{http_route=\"/api/checkout\",http_response_status_code=~\"5..\"}[28d])) / sum(increase(http_server_request_duration_seconds_count{http_route=\"/api/checkout\"}[28d]))) / 0.0005)",
        "legendFormat": "Error Budget %"
      }]
    }
  ]
}
```

### 4.3 Performance View Dashboard (`cup-performance`)

Key panels use the **time series** panel type with SLO threshold annotations.

```json
{
  "uid": "cup-performance",
  "title": "Astronomy Shop — CUP Performance (P95/P99)",
  "refresh": "30s",
  "panels": [
    {
      "id": 20,
      "type": "timeseries",
      "title": "CUP 1 — POST /api/checkout Latency (P50 / P95 / P99)",
      "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
      "fieldConfig": {
        "defaults": {"unit": "s"},
        "overrides": [
          {"matcher": {"id": "byName", "options": "P95"}, "properties": [{"id": "color", "value": {"fixedColor": "orange", "mode": "fixed"}}]},
          {"matcher": {"id": "byName", "options": "P99"}, "properties": [{"id": "color", "value": {"fixedColor": "red", "mode": "fixed"}}]}
        ]
      },
      "targets": [
        {
          "expr": "histogram_quantile(0.50, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route=\"/api/checkout\",http_request_method=\"POST\"}[5m])))",
          "legendFormat": "P50"
        },
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route=\"/api/checkout\",http_request_method=\"POST\"}[5m])))",
          "legendFormat": "P95"
        },
        {
          "expr": "histogram_quantile(0.99, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route=\"/api/checkout\",http_request_method=\"POST\"}[5m])))",
          "legendFormat": "P99"
        }
      ],
      "options": {
        "thresholds": {
          "mode": "absolute",
          "steps": [
            {"color": "transparent", "value": null},
            {"color": "red", "value": 3.0}
          ]
        }
      }
    },
    {
      "id": 21,
      "type": "timeseries",
      "title": "CUP 1 — Downstream Service P95 Latency Breakdown",
      "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
      "fieldConfig": {"defaults": {"unit": "ms"}},
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(rpc_server_duration_milliseconds_bucket{rpc_service=\"hipstershop.PaymentService\"}[5m])))",
          "legendFormat": "Payment"
        },
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(rpc_server_duration_milliseconds_bucket{rpc_service=\"hipstershop.CartService\"}[5m])))",
          "legendFormat": "Cart"
        },
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(rpc_server_duration_milliseconds_bucket{rpc_service=\"hipstershop.CurrencyService\"}[5m])))",
          "legendFormat": "Currency"
        },
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route=\"/getquote\"}[5m]))) * 1000",
          "legendFormat": "Quote"
        }
      ]
    },
    {
      "id": 22,
      "type": "timeseries",
      "title": "CUP 2 — GET /api/products P95 Latency",
      "gridPos": {"x": 0, "y": 8, "w": 8, "h": 6},
      "fieldConfig": {"defaults": {"unit": "s"}},
      "targets": [{
        "expr": "histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route=~\"/api/products.*\",http_request_method=\"GET\"}[5m])))",
        "legendFormat": "P95"
      }],
      "options": {
        "thresholds": {"steps": [{"color": "transparent","value": null},{"color": "red","value": 0.8}]}
      }
    },
    {
      "id": 23,
      "type": "timeseries",
      "title": "CUP 3 — POST /api/cart P95 Latency",
      "gridPos": {"x": 8, "y": 8, "w": 8, "h": 6},
      "fieldConfig": {"defaults": {"unit": "s"}},
      "targets": [{
        "expr": "histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route=\"/api/cart\",http_request_method=\"POST\"}[5m])))",
        "legendFormat": "P95"
      }],
      "options": {
        "thresholds": {"steps": [{"color": "transparent","value": null},{"color": "red","value": 0.3}]}
      }
    },
    {
      "id": 24,
      "type": "timeseries",
      "title": "CUP 6 — Currency Convert P95 Latency",
      "gridPos": {"x": 16, "y": 8, "w": 8, "h": 6},
      "fieldConfig": {"defaults": {"unit": "ms"}},
      "targets": [{
        "expr": "histogram_quantile(0.95, sum by (le) (rate(rpc_server_duration_milliseconds_bucket{rpc_service=\"hipstershop.CurrencyService\",rpc_method=\"Convert\"}[5m])))",
        "legendFormat": "P95"
      }],
      "options": {
        "thresholds": {"steps": [{"color": "transparent","value": null},{"color": "red","value": 100}]}
      }
    },
    {
      "id": 25,
      "type": "timeseries",
      "title": "CUP 4 — Kafka Consumer Lag (orders topic)",
      "description": "High lag = async consumers falling behind. Accounting SLO: <1000 messages; Fraud: <2000.",
      "gridPos": {"x": 0, "y": 14, "w": 12, "h": 6},
      "targets": [
        {
          "expr": "kafka_consumer_group_lag{group=\"accounting-service\",topic=\"orders\"}",
          "legendFormat": "Accounting Lag"
        },
        {
          "expr": "kafka_consumer_group_lag{group=\"fraud-detection-service\",topic=\"orders\"}",
          "legendFormat": "Fraud Lag"
        }
      ],
      "options": {
        "thresholds": {"steps": [{"color": "transparent","value": null},{"color": "yellow","value": 1000},{"color": "red","value": 2000}]}
      }
    },
    {
      "id": 26,
      "type": "timeseries",
      "title": "CUP 7 — LLM Inference Latency (P50/P95/P99)",
      "gridPos": {"x": 12, "y": 14, "w": 12, "h": 6},
      "fieldConfig": {"defaults": {"unit": "s"}},
      "targets": [
        {
          "expr": "histogram_quantile(0.50, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route=\"/v1/chat/completions\"}[5m])))",
          "legendFormat": "P50"
        },
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route=\"/v1/chat/completions\"}[5m])))",
          "legendFormat": "P95"
        }
      ],
      "options": {
        "thresholds": {"steps": [{"color": "transparent","value": null},{"color": "red","value": 10.0}]}
      }
    }
  ]
}
```

### 4.4 Reliability View Dashboard (`cup-reliability`)

This view places canary success rate alongside real-user error rate on the same time axis to distinguish synthetic failures (infrastructure down) from real-user failures (code/data bugs).

```json
{
  "uid": "cup-reliability",
  "title": "Astronomy Shop — Reliability (Canary vs Real-User)",
  "refresh": "30s",
  "panels": [
    {
      "id": 30,
      "type": "timeseries",
      "title": "CUP 1 — Canary Success % vs Real User 5xx Rate",
      "description": "Canary dropping = synthetic probes failing (infra/network). Error rate rising with healthy canary = code regression.",
      "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
      "fieldConfig": {
        "defaults": {},
        "overrides": [
          {
            "matcher": {"id": "byName", "options": "Canary Success %"},
            "properties": [
              {"id": "color", "value": {"fixedColor": "blue", "mode": "fixed"}},
              {"id": "custom.axisPlacement", "value": "right"},
              {"id": "unit", "value": "percent"},
              {"id": "min", "value": 0},
              {"id": "max", "value": 100}
            ]
          },
          {
            "matcher": {"id": "byName", "options": "Real User 5xx Rate %"},
            "properties": [
              {"id": "color", "value": {"fixedColor": "red", "mode": "fixed"}},
              {"id": "unit", "value": "percent"}
            ]
          }
        ]
      },
      "targets": [
        {
          "datasource": {"type": "prometheus"},
          "expr": "probe_success{job=\"cup1-checkout-payment\"} * 100",
          "legendFormat": "Canary Success %"
        },
        {
          "datasource": {"type": "prometheus"},
          "expr": "100 * sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/checkout\",http_response_status_code=~\"5..\"}[5m])) / sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/checkout\"}[5m]))",
          "legendFormat": "Real User 5xx Rate %"
        }
      ]
    },
    {
      "id": 31,
      "type": "timeseries",
      "title": "CUP 2 — Canary Success % vs Real User 5xx Rate",
      "gridPos": {"x": 0, "y": 8, "w": 12, "h": 6},
      "targets": [
        {
          "expr": "probe_success{job=\"cup2-browse-discovery\"} * 100",
          "legendFormat": "Canary %"
        },
        {
          "expr": "100 * sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/products\",http_response_status_code=~\"5..\"}[5m])) / sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/products\"}[5m]))",
          "legendFormat": "5xx Rate %"
        }
      ]
    },
    {
      "id": 32,
      "type": "timeseries",
      "title": "CUP 3 — Canary Success % vs Real User 5xx Rate",
      "gridPos": {"x": 12, "y": 8, "w": 12, "h": 6},
      "targets": [
        {
          "expr": "probe_success{job=\"cup3-cart-management\"} * 100",
          "legendFormat": "Canary %"
        },
        {
          "expr": "100 * sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/cart\",http_response_status_code=~\"5..\"}[5m])) / sum(rate(http_server_request_duration_seconds_count{http_route=\"/api/cart\"}[5m]))",
          "legendFormat": "5xx Rate %"
        }
      ]
    },
    {
      "id": 33,
      "type": "logs",
      "title": "CUP 1 — Recent Error Logs (Loki)",
      "description": "Log lines from any service where cup.name=checkout_payment and level=error. Correlated to trace ID for Tempo drill-down.",
      "gridPos": {"x": 0, "y": 14, "w": 24, "h": 6},
      "targets": [{
        "datasource": {"type": "loki"},
        "expr": "{job=\"astronomy-shop\"} |= \"checkout_payment\" | json | level=~\"error|ERROR\" | line_format \"{{.level}} {{.service_name}} {{.span_id}} {{.message}}\""
      }],
      "options": {
        "showTime": true,
        "dedupStrategy": "none"
      }
    },
    {
      "id": 34,
      "type": "table",
      "title": "Canary Status Summary — All CUPs",
      "description": "Current success % per canary job over the last 15 minutes.",
      "gridPos": {"x": 0, "y": 20, "w": 24, "h": 5},
      "targets": [{
        "datasource": {"type": "prometheus"},
        "expr": "avg_over_time(probe_success{job=~\"cup.*\"}[15m]) * 100",
        "legendFormat": "{{job}}",
        "instant": true,
        "format": "table"
      }],
      "transformations": [
        {"id": "organize", "options": {
          "renameByName": {"Value": "Success %", "job": "CUP Canary"}
        }}
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "thresholds": {
            "steps": [
              {"color": "red", "value": 0},
              {"color": "yellow", "value": 80},
              {"color": "green", "value": 95}
            ]
          },
          "custom": {"displayMode": "color-background"}
        }
      }
    }
  ]
}
```

### 4.5 Trace Correlation — Tempo Integration

The critical link between a canary failure and a root cause trace uses **Grafana's data link** feature to embed Tempo queries directly in metric panels.

```json
{
  "links": [
    {
      "title": "View traces for ${__field.labels.http_route}",
      "url": "/explore?orgId=1&left={\"datasource\":\"tempo\",\"queries\":[{\"queryType\":\"traceql\",\"query\":\"{.cup.name=\\\"${cup_name}\\\" && status=error}\"}],\"range\":{\"from\":\"${__value.time:date:iso}-5m\",\"to\":\"${__value.time:date:iso}+5m\"}}",
      "targetBlank": true
    }
  ]
}
```

This means that when a latency spike appears on a P95 panel, a single click opens Tempo filtered to:
- `cup.name = <selected CUP>` 
- `status = error`
- Time window: ±5 minutes around the clicked data point

**TraceQL example** for Tempo Explore (manual investigation):
```
{ .cup.name = "checkout_payment" && .http.response.status_code >= 500 }
| rate()
```

### 4.6 Grafana Alerting Rules

Grafana-native alert rules for CUP SLO breaches use the Prometheus data source with multi-condition evaluation.

```yaml
# provisioning/alerting/cup-alerts.yaml
groups:
  - name: cup-slo-alerts
    folder: SLO Alerts
    interval: 1m
    rules:
      - uid: cup1-availability
        title: "CUP 1 — Checkout Availability Below SLO"
        condition: C
        data:
          - refId: A
            queryType: ""
            relativeTimeRange: {from: 300, to: 0}
            datasourceUid: prometheus
            model:
              expr: |
                sum(rate(http_server_request_duration_seconds_count{
                  http_route="/api/checkout",
                  http_response_status_code!~"5.."}[5m]))
                /
                sum(rate(http_server_request_duration_seconds_count{
                  http_route="/api/checkout"}[5m]))
          - refId: C
            datasourceUid: __expr__
            model:
              type: threshold
              conditions:
                - evaluator: {type: lt, params: [0.9995]}
                  query: {params: [A]}
        noDataState: NoData
        execErrState: Error
        for: 2m
        labels:
          severity: critical
          cup: "1"
        annotations:
          summary: "Checkout availability {{ $values.A.Value | humanizePercentage }} < 99.95% SLO"
          runbook: "https://runbooks/cup1-checkout"

      - uid: cup1-latency-p95
        title: "CUP 1 — Checkout P95 Latency Exceeds 3s"
        condition: C
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: |
                histogram_quantile(0.95,
                  sum by (le) (rate(http_server_request_duration_seconds_bucket{
                    http_route="/api/checkout",http_request_method="POST"}[5m])))
          - refId: C
            datasourceUid: __expr__
            model:
              type: threshold
              conditions:
                - evaluator: {type: gt, params: [3.0]}
                  query: {params: [A]}
        for: 5m
        labels:
          severity: warning
          cup: "1"
        annotations:
          summary: "Checkout P95 latency {{ $values.A.Value | humanizeDuration }} > 3s SLO"

      - uid: cup3-cart-availability
        title: "CUP 3 — Cart Availability Below SLO"
        condition: C
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: |
                sum(rate(http_server_request_duration_seconds_count{
                  http_route="/api/cart",http_response_status_code!~"5.."}[5m]))
                /
                sum(rate(http_server_request_duration_seconds_count{
                  http_route="/api/cart"}[5m]))
          - refId: C
            datasourceUid: __expr__
            model:
              type: threshold
              conditions:
                - evaluator: {type: lt, params: [0.9995]}
                  query: {params: [A]}
        for: 2m
        labels:
          severity: critical
          cup: "3"
```

---

## Summary Reference

| CUP | Canary Type | Script Type | Schedule | Availability SLO | P95 Latency |
|---|---|---|---|---|---|
| 1 — Checkout & Payment | Workflow (6 steps) | k6 Browser | Every 5 min | 99.95% | 3,000 ms |
| 2 — Product Browse | Workflow (4 steps) | k6 Browser | Every 5 min | 99.9% | 800 ms |
| 3 — Cart Management | Workflow (3 steps) | k6 Scripted HTTP | Every 5 min | 99.95% | 300 ms |
| 4 — Order Fulfillment | Heartbeat (1 probe) | HTTP | Every 5 min | 99.9% | 800 ms |
| 5 — Shipping Quote | Heartbeat (1 probe) | HTTP | Every 5 min | 99.9% | 600 ms |
| 6 — Currency | Heartbeat (1 probe) | HTTP | Every 5 min | 99.95% | 100 ms |
| 7 — AI Assistant | Workflow (2 steps) | k6 Scripted HTTP | Every 10 min | 99.0% | 10,000 ms |
| 8 — Product Reviews | Workflow (2 steps) | k6 Scripted HTTP | Every 5 min | 99.5% | 500 ms |