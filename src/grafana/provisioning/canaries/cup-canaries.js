/**
 * Astronomy Shop — Critical User Path Synthetic Canaries
 * Grafana k6 / Synthetic Monitoring scripts
 *
 * Each exported function corresponds to one CUP canary check.
 * Run individually via:
 *   k6 run --env BASE_URL=http://localhost:8080 cup-canaries.js --export <function>
 *
 * When deployed in Grafana Cloud Synthetic Monitoring the checks map to:
 *   cup1-checkout-payment   → checkoutWorkflow()
 *   cup2-browse-discovery   → browseDiscovery()
 *   cup3-cart-management    → cartManagement()
 *   cup4-order-fulfillment  → orderFulfillment()
 *   cup5-shipping-quote     → shippingQuote()
 *   cup6-currency           → currencyDisplay()
 *   cup7-ai-assistant       → aiAssistant()
 *   cup8-product-reviews    → productReviews()
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// ─── Shared configuration ────────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || "http://frontend-proxy:8080";
const GRPC_BASE = __ENV.GRPC_BASE || "http://frontend-proxy:8080"; // gRPC-Web via proxy

// Custom SLO metrics (reported as Prometheus metrics when running in Grafana SM)
const cup1CheckoutSuccess = new Rate("cup1_checkout_success");
const cup1CheckoutDuration = new Trend("cup1_checkout_duration_ms");
const cup2BrowseSuccess = new Rate("cup2_browse_success");
const cup2BrowseDuration = new Trend("cup2_browse_duration_ms");
const cup3CartSuccess = new Rate("cup3_cart_success");
const cup3CartDuration = new Trend("cup3_cart_duration_ms");
const cup4FulfillSuccess = new Rate("cup4_fulfillment_success");
const cup5QuoteSuccess = new Rate("cup5_shipping_quote_success");
const cup5QuoteDuration = new Trend("cup5_shipping_quote_duration_ms");
const cup6CurrencySuccess = new Rate("cup6_currency_success");
const cup6CurrencyDuration = new Trend("cup6_currency_duration_ms");
const cup7AISuccess = new Rate("cup7_ai_success");
const cup7AIDuration = new Trend("cup7_ai_duration_ms");
const cup8ReviewSuccess = new Rate("cup8_review_success");
const cup8ReviewDuration = new Trend("cup8_review_duration_ms");

// ─── Common headers ───────────────────────────────────────────────────────────
const JSON_HEADERS = {
  "Content-Type": "application/json",
  Accept: "application/json",
};

// ─────────────────────────────────────────────────────────────────────────────
// CUP 1 — Checkout & Payment Workflow
// SLO: 99.95% availability, P95 < 3,000 ms
//
// Steps:
//  1. GET /api/products          → pick a product
//  2. POST /api/cart             → add to cart
//  3. GET /api/cart?sessionId=X  → verify cart contents
//  4. POST /api/checkout         → place order (full checkout)
//  5. Assert HTTP 200 + orderId present in response body
// ─────────────────────────────────────────────────────────────────────────────
export function checkoutWorkflow() {
  const sessionId = `canary-cup1-${Date.now()}`;
  const params = { headers: JSON_HEADERS, timeout: "10s" };

  // Step 1: List products
  const productsRes = http.get(`${BASE_URL}/api/products`, params);
  const productsOk = check(productsRes, {
    "CUP1 Step1 products 200": (r) => r.status === 200,
    "CUP1 Step1 products has items": (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.products) && body.products.length > 0;
      } catch (_) {
        return false;
      }
    },
  });
  if (!productsOk) {
    cup1CheckoutSuccess.add(0);
    return;
  }

  const products = JSON.parse(productsRes.body).products;
  const productId = products[0].id;

  // Step 2: Add to cart
  const addCartRes = http.post(
    `${BASE_URL}/api/cart`,
    JSON.stringify({
      userId: sessionId,
      item: { productId, quantity: 1 },
    }),
    params
  );
  check(addCartRes, { "CUP1 Step2 add-cart 200": (r) => r.status === 200 });

  // Step 3: Read cart back
  const getCartRes = http.get(
    `${BASE_URL}/api/cart?sessionId=${sessionId}`,
    params
  );
  check(getCartRes, { "CUP1 Step3 get-cart 200": (r) => r.status === 200 });

  // Step 4: Place checkout order
  const checkoutPayload = JSON.stringify({
    userId: sessionId,
    userCurrency: "USD",
    address: {
      streetAddress: "1600 Amphitheatre Parkway",
      city: "Mountain View",
      state: "CA",
      country: "USA",
      zipCode: "94043",
    },
    email: "canary@astronomy.shop",
    creditCard: {
      creditCardNumber: "4432-8015-6152-0454",
      creditCardCvv: 672,
      creditCardExpirationYear: 2030,
      creditCardExpirationMonth: 1,
    },
  });

  const start = Date.now();
  const checkoutRes = http.post(
    `${BASE_URL}/api/checkout`,
    checkoutPayload,
    params
  );
  const durationMs = Date.now() - start;

  const success = check(checkoutRes, {
    "CUP1 Step4 checkout 200": (r) => r.status === 200,
    "CUP1 Step4 checkout orderId present": (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.orderId === "string" && body.orderId.length > 0;
      } catch (_) {
        return false;
      }
    },
    "CUP1 Step4 checkout P95 < 3000ms": () => durationMs < 3000,
  });

  cup1CheckoutSuccess.add(success ? 1 : 0);
  cup1CheckoutDuration.add(durationMs);

  sleep(1);
}

// ─────────────────────────────────────────────────────────────────────────────
// CUP 2 — Product Browse & Discovery
// SLO: 99.9% availability, P95 < 800 ms
//
// Steps:
//  1. GET /api/products              → list all products
//  2. GET /api/products/:id          → get product detail
//  3. Assert HTTP 200, product fields present, response < 800ms
// ─────────────────────────────────────────────────────────────────────────────
export function browseDiscovery() {
  const params = { headers: JSON_HEADERS, timeout: "5s" };

  // Step 1: List products
  const start1 = Date.now();
  const listRes = http.get(`${BASE_URL}/api/products`, params);
  const listDuration = Date.now() - start1;

  const listOk = check(listRes, {
    "CUP2 list products 200": (r) => r.status === 200,
    "CUP2 list products has body": (r) => r.body && r.body.length > 2,
    "CUP2 list products P95 < 800ms": () => listDuration < 800,
  });

  cup2BrowseSuccess.add(listOk ? 1 : 0);
  cup2BrowseDuration.add(listDuration);

  if (!listOk) return;

  // Step 2: Get a single product
  let productId;
  try {
    const body = JSON.parse(listRes.body);
    productId = body.products[0].id;
  } catch (_) {
    cup2BrowseSuccess.add(0);
    return;
  }

  const start2 = Date.now();
  const detailRes = http.get(`${BASE_URL}/api/products/${productId}`, params);
  const detailDuration = Date.now() - start2;

  const detailOk = check(detailRes, {
    "CUP2 product detail 200": (r) => r.status === 200,
    "CUP2 product detail has name": (r) => {
      try {
        return JSON.parse(r.body).product?.name?.length > 0;
      } catch (_) {
        return false;
      }
    },
    "CUP2 product detail P95 < 800ms": () => detailDuration < 800,
  });

  cup2BrowseSuccess.add(detailOk ? 1 : 0);
  cup2BrowseDuration.add(detailDuration);

  sleep(1);
}

// ─────────────────────────────────────────────────────────────────────────────
// CUP 3 — Shopping Cart Management
// SLO: 99.95% availability, P95 < 300 ms
//
// Steps:
//  1. POST /api/cart     → add item
//  2. GET  /api/cart     → read cart
//  3. DELETE /api/cart   → empty cart
//  4. Assert each step 200, total < 300ms per operation
// ─────────────────────────────────────────────────────────────────────────────
export function cartManagement() {
  const sessionId = `canary-cup3-${Date.now()}`;
  const params = { headers: JSON_HEADERS, timeout: "5s" };

  // Step 1: Add item
  const addStart = Date.now();
  const addRes = http.post(
    `${BASE_URL}/api/cart`,
    JSON.stringify({
      userId: sessionId,
      item: { productId: "OLJCESPC7Z", quantity: 1 },
    }),
    params
  );
  const addDuration = Date.now() - addStart;

  const addOk = check(addRes, {
    "CUP3 add to cart 200": (r) => r.status === 200,
    "CUP3 add to cart P95 < 300ms": () => addDuration < 300,
  });

  // Step 2: Get cart
  const getStart = Date.now();
  const getRes = http.get(
    `${BASE_URL}/api/cart?sessionId=${sessionId}`,
    params
  );
  const getDuration = Date.now() - getStart;

  const getOk = check(getRes, {
    "CUP3 get cart 200": (r) => r.status === 200,
    "CUP3 get cart P95 < 300ms": () => getDuration < 300,
  });

  // Step 3: Empty cart
  const deleteStart = Date.now();
  const deleteRes = http.del(
    `${BASE_URL}/api/cart`,
    JSON.stringify({ userId: sessionId }),
    params
  );
  const deleteDuration = Date.now() - deleteStart;

  const deleteOk = check(deleteRes, {
    "CUP3 empty cart 200": (r) => r.status === 200,
    "CUP3 empty cart P95 < 300ms": () => deleteDuration < 300,
  });

  const allOk = addOk && getOk && deleteOk;
  cup3CartSuccess.add(allOk ? 1 : 0);
  cup3CartDuration.add(Math.max(addDuration, getDuration, deleteDuration));

  sleep(1);
}

// ─────────────────────────────────────────────────────────────────────────────
// CUP 4 — Order Fulfillment (async post-checkout)
// SLO: ShipOrder gRPC 99.9%; Kafka consumer lag < 1,000 msgs
//
// This heartbeat check verifies the checkout→fulfillment path by:
//  1. Posting a test checkout order (same as CUP1)
//  2. Asserting orderId is returned (Kafka message enqueued)
//  Note: Kafka lag itself is monitored via real metrics in Prometheus.
// ─────────────────────────────────────────────────────────────────────────────
export function orderFulfillment() {
  const sessionId = `canary-cup4-${Date.now()}`;
  const params = { headers: JSON_HEADERS, timeout: "15s" };

  // Seed cart first
  http.post(
    `${BASE_URL}/api/cart`,
    JSON.stringify({
      userId: sessionId,
      item: { productId: "OLJCESPC7Z", quantity: 1 },
    }),
    params
  );

  // Full checkout to trigger fulfillment pipeline
  const start = Date.now();
  const res = http.post(
    `${BASE_URL}/api/checkout`,
    JSON.stringify({
      userId: sessionId,
      userCurrency: "USD",
      address: {
        streetAddress: "1 Infinite Loop",
        city: "Cupertino",
        state: "CA",
        country: "USA",
        zipCode: "95014",
      },
      email: "canary-cup4@astronomy.shop",
      creditCard: {
        creditCardNumber: "4432-8015-6152-0454",
        creditCardCvv: 672,
        creditCardExpirationYear: 2030,
        creditCardExpirationMonth: 1,
      },
    }),
    params
  );
  const durationMs = Date.now() - start;

  const success = check(res, {
    "CUP4 checkout returns orderId": (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.orderId === "string" && body.orderId.length > 0;
      } catch (_) {
        return false;
      }
    },
    "CUP4 checkout 200": (r) => r.status === 200,
  });

  cup4FulfillSuccess.add(success ? 1 : 0);

  sleep(2);
}

// ─────────────────────────────────────────────────────────────────────────────
// CUP 5 — Shipping Quote
// SLO: 99.9% availability, P95 < 600 ms
//
// Steps:
//  1. POST /getquote with item list
//  2. Assert HTTP 200, costUsd present, duration < 600ms
// ─────────────────────────────────────────────────────────────────────────────
export function shippingQuote() {
  const params = { headers: JSON_HEADERS, timeout: "5s" };

  const payload = JSON.stringify({
    address: {
      streetAddress: "1600 Amphitheatre Parkway",
      city: "Mountain View",
      state: "CA",
      country: "USA",
      zipCode: "94043",
    },
    items: [{ productId: "OLJCESPC7Z", quantity: 2 }],
  });

  const start = Date.now();
  const res = http.post(`${BASE_URL}/getquote`, payload, params);
  const durationMs = Date.now() - start;

  const success = check(res, {
    "CUP5 getquote 200": (r) => r.status === 200,
    "CUP5 getquote has costUsd": (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.costUsd !== undefined || body.cost_usd !== undefined;
      } catch (_) {
        return false;
      }
    },
    "CUP5 getquote P95 < 600ms": () => durationMs < 600,
  });

  cup5QuoteSuccess.add(success ? 1 : 0);
  cup5QuoteDuration.add(durationMs);

  sleep(1);
}

// ─────────────────────────────────────────────────────────────────────────────
// CUP 6 — Currency Selection & Price Display
// SLO: 99.95% availability, P95 < 100 ms
//
// Steps:
//  1. GET /api/currencies  → list supported currencies
//  2. GET /api/products    → verify prices returned (implicit currency call)
//  3. Assert currencies list non-empty, product prices present, < 100ms
// ─────────────────────────────────────────────────────────────────────────────
export function currencyDisplay() {
  const params = { headers: JSON_HEADERS, timeout: "3s" };

  // Step 1: List currencies
  const start = Date.now();
  const currencyRes = http.get(`${BASE_URL}/api/currencies`, params);
  const durationMs = Date.now() - start;

  const currencyOk = check(currencyRes, {
    "CUP6 get currencies 200": (r) => r.status === 200,
    "CUP6 currencies has entries": (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.currencies) && body.currencies.length > 0;
      } catch (_) {
        return false;
      }
    },
    "CUP6 currencies P95 < 100ms": () => durationMs < 100,
  });

  cup6CurrencySuccess.add(currencyOk ? 1 : 0);
  cup6CurrencyDuration.add(durationMs);

  // Step 2: Check products come back with prices
  const productsRes = http.get(`${BASE_URL}/api/products`, params);
  const pricesOk = check(productsRes, {
    "CUP6 products 200": (r) => r.status === 200,
    "CUP6 products have priceUsd": (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.products?.[0]?.priceUsd !== undefined;
      } catch (_) {
        return false;
      }
    },
  });

  cup6CurrencySuccess.add(pricesOk ? 1 : 0);

  sleep(1);
}

// ─────────────────────────────────────────────────────────────────────────────
// CUP 7 — AI Product Assistant
// SLO: 99.0% availability, P95 < 10,000 ms
//
// Steps:
//  1. POST /v1/chat/completions with a product question
//  2. Assert HTTP 200, response has choices, < 10,000ms
// ─────────────────────────────────────────────────────────────────────────────
export function aiAssistant() {
  const params = { headers: JSON_HEADERS, timeout: "30s" };

  const payload = JSON.stringify({
    model: "gpt-3.5-turbo",
    messages: [
      {
        role: "user",
        content:
          "What telescopes do you have in stock? Give me a one-sentence answer.",
      },
    ],
    max_tokens: 50,
    temperature: 0.0,
  });

  const start = Date.now();
  const res = http.post(`${BASE_URL}/v1/chat/completions`, payload, params);
  const durationMs = Date.now() - start;

  const success = check(res, {
    "CUP7 chat/completions 200": (r) => r.status === 200,
    "CUP7 chat/completions has choices": (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.choices) && body.choices.length > 0;
      } catch (_) {
        return false;
      }
    },
    "CUP7 chat/completions P95 < 10000ms": () => durationMs < 10000,
  });

  cup7AISuccess.add(success ? 1 : 0);
  cup7AIDuration.add(durationMs);

  sleep(2);
}

// ─────────────────────────────────────────────────────────────────────────────
// CUP 8 — Product Reviews
// SLO: 99.5% availability, P95 < 500 ms
//
// Steps:
//  1. GET /api/products        → pick a product id
//  2. GET /api/reviews/:id     → list reviews
//  3. Assert HTTP 200, reviews array present, < 500ms
// ─────────────────────────────────────────────────────────────────────────────
export function productReviews() {
  const params = { headers: JSON_HEADERS, timeout: "5s" };

  // Step 1: Get product list for a real ID
  const productsRes = http.get(`${BASE_URL}/api/products`, params);
  if (!check(productsRes, { "CUP8 products 200": (r) => r.status === 200 })) {
    cup8ReviewSuccess.add(0);
    return;
  }

  let productId;
  try {
    const body = JSON.parse(productsRes.body);
    productId = body.products[0].id;
  } catch (_) {
    cup8ReviewSuccess.add(0);
    return;
  }

  // Step 2: List reviews
  const start = Date.now();
  const reviewsRes = http.get(`${BASE_URL}/api/reviews/${productId}`, params);
  const durationMs = Date.now() - start;

  const success = check(reviewsRes, {
    "CUP8 reviews 200": (r) => r.status === 200,
    "CUP8 reviews has body": (r) => r.body && r.body.length > 2,
    "CUP8 reviews P95 < 500ms": () => durationMs < 500,
  });

  cup8ReviewSuccess.add(success ? 1 : 0);
  cup8ReviewDuration.add(durationMs);

  sleep(1);
}

// ─────────────────────────────────────────────────────────────────────────────
// Default export — runs all canary checks sequentially.
// Use this for local smoke-testing; in Grafana SM each function is scheduled
// independently per the Terraform configuration.
// ─────────────────────────────────────────────────────────────────────────────
export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    cup1_checkout_success: ["rate>=0.9995"],
    cup2_browse_success: ["rate>=0.999"],
    cup3_cart_success: ["rate>=0.9995"],
    cup4_fulfillment_success: ["rate>=0.999"],
    cup5_shipping_quote_success: ["rate>=0.999"],
    cup6_currency_success: ["rate>=0.9995"],
    cup7_ai_success: ["rate>=0.99"],
    cup8_review_success: ["rate>=0.995"],
    cup1_checkout_duration_ms: ["p(95)<3000"],
    cup2_browse_duration_ms: ["p(95)<800"],
    cup3_cart_duration_ms: ["p(95)<300"],
    cup5_shipping_quote_duration_ms: ["p(95)<600"],
    cup6_currency_duration_ms: ["p(95)<100"],
    cup7_ai_duration_ms: ["p(95)<10000"],
    cup8_review_duration_ms: ["p(95)<500"],
  },
};

export default function () {
  checkoutWorkflow();
  browseDiscovery();
  cartManagement();
  orderFulfillment();
  shippingQuote();
  currencyDisplay();
  aiAssistant();
  productReviews();
}