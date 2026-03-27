# Critical User Paths — SLO, Canaries & Dashboard Implementation Summary

## Overview

This document summarises all actions taken to implement SLOs, synthetic canaries, and Grafana dashboards for the Astronomy Shop's 8 Critical User Paths (CUPs), as specified in:

- `doc/CRITICAL_USER_PATHS_ANALYSIS.md`
- `doc/CRITICAL_USER_PATHS_CANARIES_AND_DASHBOARD_PLAN.md`

---

## Files Created

All files live under `src/grafana/provisioning/` and are loaded automatically by Grafana at startup.

| File | Description |
|------|-------------|
| `dashboards/slo.yaml` | Dashboard provider — tells Grafana to scan `dashboards/slo/` |
| `dashboards/slo/cup-executive.json` | Executive SLO overview: availability stat grid, error budget heat-map |
| `dashboards/slo/cup-performance.json` | Latency P50/P95/P99 per CUP, request rate, service decomposition |
| `dashboards/slo/cup-reliability.json` | Error budget burn-rate, canary status, SLO compliance table |
| `alerting/cup-slo-alerts.yml` | Fast-burn + slow-burn alert rules for all 8 CUPs |
| `synthetic-monitoring/cup-canaries.yaml` | 8 HTTP heartbeat checks, one per CUP (native Grafana SM provisioning) |
| `canaries/cup-canaries.js` | Multi-step workflow canary scripts exercising full HTTP journeys |

---

## CUP Coverage

### CUP 1 — Checkout & Payment (P0 — Critical)
- **SLI**: `POST /api/checkout` 5xx error rate
- **SLO Target**: 99.95% availability / 28-day window; P95 latency < 3,000 ms
- **Alert rules**: Fast-burn (14× in 5 min), slow-burn (1× in 6 h)
- **Canary**: Heartbeat POST `/api/checkout` every 60 s; multi-step workflow (browse → cart add → checkout) in `cup-canaries.js`
- **Dashboard panels**: Availability stat, P95 latency time-series, error budget gauge

### CUP 2 — Product Browse & Discovery (P1 — High)
- **SLI**: `GET /api/products` + `GET /api/products/{id}` 5xx rate
- **SLO Target**: 99.9% availability / 28-day window; P95 < 800 ms
- **Alert rules**: Fast-burn (14×/5 min), slow-burn (1×/6 h)
- **Canary**: Heartbeat GET `/api/products` every 60 s; product detail probe in workflow script
- **Dashboard panels**: Browse availability, P95 latency

### CUP 3 — Shopping Cart Management (P0 — Critical)
- **SLI**: `/api/cart` POST/GET/DELETE 5xx error rate
- **SLO Target**: 99.95% availability / 28-day window; P95 < 300 ms
- **Alert rules**: Fast-burn (14×/5 min), slow-burn (1×/6 h)
- **Canary**: Heartbeat POST `/api/cart` every 60 s; add/get/clear cart sequence in workflow script
- **Dashboard panels**: Cart availability, P95 latency

### CUP 4 — Order Fulfillment (P0 — Critical)
- **SLI**: CheckoutService gRPC success rate + Kafka consumer lag
- **SLO Target**: 99.9% availability; Kafka lag < 1,000 messages
- **Alert rules**: Fast-burn (14×/5 min) on gRPC error rate; Kafka lag threshold alert
- **Canary**: Full checkout probe every 120 s (heavier) triggering async pipeline
- **Dashboard panels**: Fulfillment gRPC success rate, Kafka lag gauge

### CUP 5 — Shipping Quote (P1 — High)
- **SLI**: QuoteService gRPC + `POST /getquote` HTTP success rate
- **SLO Target**: 99.9% availability; P95 < 600 ms
- **Alert rules**: Fast-burn (14×/5 min), slow-burn (1×/6 h)
- **Canary**: Heartbeat POST `/getquote` every 60 s; quote retrieval in workflow script
- **Dashboard panels**: Shipping quote availability, P95 latency

### CUP 6 — Currency Selection & Price Display (P1 — High)
- **SLI**: CurrencyService gRPC success rate (status_code = 0)
- **SLO Target**: 99.95% availability; P95 < 100 ms
- **Alert rules**: Fast-burn (14×/5 min), slow-burn (1×/6 h)
- **Canary**: Heartbeat GET `/api/currencies` every 60 s; body assertion: `USD` present
- **Dashboard panels**: Currency service availability, gRPC P95 latency

### CUP 7 — AI Product Assistant (P2 — Medium)
- **SLI**: LLM service `POST /v1/chat/completions` 5xx error rate
- **SLO Target**: 99.0% availability; P95 < 10,000 ms
- **Alert rules**: Fast-burn (14×/5 min), slow-burn (1×/6 h) — relaxed thresholds
- **Canary**: Heartbeat POST `/v1/chat/completions` every 300 s (cost-limited); body assertion: `choices` present
- **Dashboard panels**: AI assistant availability, P95 token-generation latency

### CUP 8 — Product Reviews (P2 — Medium)
- **SLI**: ProductReviews `GET /api/reviews/{productId}` 5xx error rate
- **SLO Target**: 99.5% availability; P95 < 500 ms
- **Alert rules**: Fast-burn (14×/5 min), slow-burn (1×/6 h)
- **Canary**: Heartbeat GET `/api/reviews/OLJCESPC7Z` every 60 s; body assertion: `reviews` present
- **Dashboard panels**: Reviews availability, P95 latency

---

## Dashboards

### Executive SLO Overview (`cup-executive.json`)
- 8-panel availability stat grid (one stat per CUP, green/amber/red thresholds)
- Error budget heat-map across all CUPs
- Top-level availability time-series (7-day / 28-day toggle)
- Incident rate counter

### Performance Dashboard (`cup-performance.json`)
- P50 / P95 / P99 latency time-series per CUP
- Latency SLO threshold reference lines
- Request rate and throughput per service
- Service dependency breakdown (frontend-proxy → checkout → cart → currency)

### Reliability Dashboard (`cup-reliability.json`)
- Error budget burn-rate panels (fast-burn and slow-burn rates)
- 28-day error budget remaining gauge per CUP
- Synthetic canary success rate (from `probe_success` metric)
- SLO compliance table — current availability vs. target

---

## Alert Rules (`cup-slo-alerts.yml`)

Two alert rules per CUP — fast-burn (paging) and slow-burn (warning):

| Severity | Condition | Channels |
|----------|-----------|---------|
| Critical | Fast-burn: >14× error budget burn rate for >5 min | PagerDuty / on-call |
| Warning | Slow-burn: >1× burn rate sustained for >6 h | Slack / email |

Labels on each rule: `cup`, `cup_name`, `severity` — used for dashboard variable filtering and alert routing.

---

## Synthetic Canaries

### Heartbeat Checks (`synthetic-monitoring/cup-canaries.yaml`)

Native Grafana SM provisioning YAML. Loaded at Grafana startup — no API calls or external tooling required.

| CUP | Job | Target | Frequency | Timeout | Body Assertion |
|-----|-----|--------|-----------|---------|---------------|
| 1 | cup1-checkout-payment | POST /api/checkout | 60 s | 10 s | HTTP 200/201 |
| 2 | cup2-browse-discovery | GET /api/products | 60 s | 5 s | `"id"` present |
| 3 | cup3-cart-management | POST /api/cart | 60 s | 5 s | HTTP 200/201 |
| 4 | cup4-order-fulfillment | POST /api/checkout | 120 s | 15 s | HTTP 200/201 |
| 5 | cup5-shipping-quote | POST /getquote | 60 s | 5 s | `"costUsd"` present |
| 6 | cup6-currency | GET /api/currencies | 60 s | 3 s | `USD` present |
| 7 | cup7-ai-assistant | POST /v1/chat/completions | 300 s | 30 s | `"choices"` present |
| 8 | cup8-product-reviews | GET /api/reviews/:id | 60 s | 5 s | `"reviews"` present |

Probes run from 3 geographic locations by default: **Sydney**, **Frankfurt**, **Chicago**.  
Override the target base URL via environment variable: `FRONTEND_URL` (default: `http://frontend-proxy:8080`).

### Multi-Step Workflow Canaries (`canaries/cup-canaries.js`)

Node.js scripts exercising full user journeys end-to-end:

| Function | Journey |
|---------|---------|
| `runCup1CheckoutWorkflow` | Browse products → add to cart → submit checkout → verify order |
| `runCup2BrowseWorkflow` | List products → get product detail → verify response schema |
| `runCup3CartWorkflow` | Add item → get cart → remove item → verify empty cart |
| `runCup4FulfillmentWorkflow` | Full checkout → verify async pipeline response |
| `runCup5ShippingWorkflow` | Get shipping quote with address → verify cost > 0 |
| `runCup6CurrencyWorkflow` | List currencies → verify USD/EUR/CAD present |
| `runCup7AIWorkflow` | Send chat prompt → verify non-empty response |
| `runCup8ReviewsWorkflow` | Get reviews → verify schema → post review (if write-enabled) |

---

## SLO Targets Summary

| CUP | Name | Priority | Availability SLO | P95 Latency SLO | Window |
|-----|------|----------|-----------------|-----------------|--------|
| 1 | Checkout & Payment | P0 | 99.95% | 3,000 ms | 28d |
| 2 | Browse & Discovery | P1 | 99.9% | 800 ms | 28d |
| 3 | Cart Management | P0 | 99.95% | 300 ms | 28d |
| 4 | Order Fulfillment | P0 | 99.9% | — | 28d |
| 5 | Shipping Quote | P1 | 99.9% | 600 ms | 28d |
| 6 | Currency Display | P1 | 99.95% | 100 ms | 28d |
| 7 | AI Assistant | P2 | 99.0% | 10,000 ms | 28d |
| 8 | Product Reviews | P2 | 99.5% | 500 ms | 28d |

---

## Deployment

Everything is loaded by Grafana via its native provisioning mechanism — no external tooling required.

```bash
# Apply all provisioning (dashboards, alerts, canaries)
docker compose restart grafana
```

### Validation

```bash
# Dashboards loaded in CUP SLO folder
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_URL/api/search?folderTitle=CUP+SLO" | jq '.[].title'

# Alert rules provisioned
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_URL/api/ruler/grafana/api/v1/rules/CUP%20SLO" | jq 'keys'

# Run workflow canaries manually
node src/grafana/provisioning/canaries/cup-canaries.js
```

---

## Architecture Alignment

| Concern | Implementation |
|---------|---------------|
| Metrics collection | OTel Collector → Prometheus (existing `otel-config.yml`) |
| Trace propagation | Existing OTel SDK instrumentation per service |
| SLI computation | PromQL ratio queries in alert rules and dashboard panels |
| Burn-rate alerting | Grafana Unified Alerting — multi-window burn-rate rules |
| Synthetic monitoring | Grafana SM native YAML provisioning — HTTP checks from 3 geographic probes |
| Dashboard provisioning | Grafana YAML/JSON provisioning — no manual UI steps |
| Alert routing | Grafana notification policy — severity label-based routing |