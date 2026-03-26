# Astronomy Shop – API Endpoint Discovery Summary

> **Source:** `doc/endpoint.csv`  
> **Scope:** All services under `src/` in the OpenTelemetry Demo repository.  
> **Reference:** `doc/application-overview.md`

---

## Overview Counts

| Category | Count |
|---|---|
| Total endpoints discovered | 62 |
| External (publicly reachable via Envoy :8080) | 24 |
| Internal (service-mesh only) | 38 |
| Public-facing (designed for end users) | 12 |
| Endpoints with security warnings | 18 |
| gRPC methods | 18 |
| HTTP REST endpoints | 44 |

---

## Endpoints by Service / Folder

| Folder | Endpoint Count | Protocol | Notes |
|---|---|---|---|
| `frontend-proxy` | 10 | HTTP (Envoy routes) | All external traffic passes through here |
| `frontend` | 13 | HTTP REST (Next.js BFF) | Browser-facing API; proxies to backend gRPC/HTTP |
| `product-catalog` | 3 | gRPC | Internal service on :3550 |
| `cart` | 3 | gRPC | Internal service on :7070 |
| `checkout` | 1 | gRPC | Internal orchestrator on :5050 |
| `currency` | 2 | gRPC | Internal service on :7001 |
| `payment` | 1 | gRPC | Internal service on :50051 |
| `shipping` | 2 | gRPC | Internal service on :50050 |
| `email` | 2 | gRPC + HTTP | Internal service on :6060 |
| `recommendation` | 1 | gRPC | Internal service on :9001 |
| `ad` | 1 | gRPC | Internal service on :9555 |
| `product-reviews` | 2 | gRPC | Internal service on :3551 |
| `quote` | 1 | HTTP | Internal service on :8090 |
| `llm` | 1 | HTTP | Internal service on :8000 |
| `flagd` | 4 | gRPC / Connect | Internal flag evaluation service on :8013 |
| `flagd-ui` | 2 | HTTP (Phoenix) | External admin UI on :4000 |
| `otel-collector` | 6 | HTTP + gRPC | Internal OTLP receiver on :4317/:4318 |
| `load-generator` | 3 | HTTP | External Locust UI on :8089 |
| `jaeger` | 3 | HTTP | External trace query API |

---

## Endpoints by Category

| Category | Count |
|---|---|
| `product` | 7 |
| `cart` | 4 |
| `checkout` | 2 |
| `payment` | 1 |
| `shipping` | 4 |
| `email` | 2 |
| `recommendation` | 2 |
| `ad` | 2 |
| `currency` | 2 |
| `review` | 3 |
| `llm` | 2 |
| `telemetry` | 11 |
| `flags` | 5 |
| `admin` | 3 |
| `load-test` | 3 |
| `proxy` | 10 |

---

## Security Warnings Summary

The following endpoints have notable security concerns in this demo setup. **These are acceptable for a demo/development environment but must be addressed before any production deployment.**

### 🔴 High Risk

| Endpoint | Folder | Issue |
|---|---|---|
| `POST /otlp-http/v1/traces` | frontend-proxy | Publicly reachable OTLP receiver — no auth; allows arbitrary span injection |
| `POST /otlp-http/v1/metrics` | frontend-proxy | Same as above for metrics |
| `POST /otlp-http/v1/logs` | frontend-proxy | Same as above for logs |
| `POST /api/data-collection` | frontend | Server-side relay of raw browser OTLP; no payload validation |
| `gRPC PaymentService/Charge` | payment | Credit card PAN + CVV transmitted in gRPC payload — must never appear in trace attributes |
| `gRPC CheckoutService/PlaceOrder` | checkout | Internally passes card data to PaymentService — risk of accidental logging |

### 🟡 Medium Risk

| Endpoint | Folder | Issue |
|---|---|---|
| `GET /jaeger/ui/*` | frontend-proxy | Jaeger UI publicly exposed without auth — reveals service topology and request traces |
| `GET /grafana/*` | frontend-proxy | Grafana publicly accessible (default admin:admin credentials) |
| `GET /prometheus/*` | frontend-proxy | Prometheus metrics endpoint publicly reachable — exposes internal labels and cardinality |
| `GET|POST /flagd-ui/*` | frontend-proxy | FlagD management UI has no auth — allows fault injection and flag manipulation |
| `GET|POST /flagd-ui/flags/[flag_id]` | flagd-ui | Modifying flags can inject failures into live services |
| `POST /v1/chat/completions` | llm | Prompt injection risk; resource exhaustion without rate limiting |
| `POST /getquote` | quote | No authentication on internal HTTP endpoint |
| `GET|POST /loadgen/*` | frontend-proxy | Load generator UI publicly reachable — allows DoS via test initiation |

### 🟢 Low Risk / Informational

| Endpoint | Folder | Issue |
|---|---|---|
| `GET /jaeger/api/traces` | jaeger | Reveals internal trace IDs and operation names |
| `GET /jaeger/api/services` | jaeger | Reveals internal service names and topology |
| `FlagD evaluation endpoints` | flagd | No default authentication on OpenFeature flag evaluation |

---

## Visibility & Exposure Summary

### Externally Reachable Endpoints (via Envoy :8080)

All external access is through the **Envoy frontend-proxy** on port 8080.

```
/                          → frontend (storefront)
/api/*                     → frontend (REST API)
/otlp-http/v1/*            → otel-collector:4318 (OTLP HTTP relay)
/jaeger/ui/*               → jaeger:16686 (trace UI)
/grafana/*                 → grafana:3000 (dashboards)
/prometheus/*              → prometheus:9090 (metrics)
/flagd-ui/*                → flagd-ui:4000 (flag management)
/loadgen/*                 → load-generator:8089 (Locust UI)
```

### Internal-Only Endpoints

All gRPC services are accessible only within the Docker/Kubernetes service network:

```
product-catalog   :3550   gRPC
cart              :7070   gRPC
checkout          :5050   gRPC
currency          :7001   gRPC
payment           :50051  gRPC
shipping          :50050  gRPC
recommendation    :9001   gRPC
ad                :9555   gRPC
email             :6060   HTTP/gRPC
product-reviews   :3551   gRPC
quote             :8090   HTTP
llm               :8000   HTTP
flagd             :8013   gRPC/Connect
otel-collector    :4317   gRPC (OTLP)
otel-collector    :4318   HTTP (OTLP)
```

---

## Communication Patterns

### Synchronous (Request/Response)

| Caller | Callee | Protocol | Endpoints |
|---|---|---|---|
| Browser | frontend-proxy → frontend | HTTP | `/`, `/api/*` |
| frontend | product-catalog | gRPC | `ListProducts`, `GetProduct`, `SearchProducts` |
| frontend | cart | gRPC | `AddItem`, `GetCart`, `EmptyCart` |
| frontend | checkout | gRPC | `PlaceOrder` |
| frontend | recommendation | gRPC | `ListRecommendations` |
| frontend | ad | gRPC | `GetAds` |
| frontend | currency | gRPC | `GetSupportedCurrencies`, `Convert` |
| frontend | product-reviews | gRPC | `ListProductReviews` |
| frontend | llm | HTTP | `POST /v1/chat/completions` |
| checkout | cart | gRPC | `GetCart`, `EmptyCart` |
| checkout | currency | gRPC | `Convert` |
| checkout | payment | gRPC | `Charge` |
| checkout | quote | HTTP | `POST /getquote` |
| checkout | email | HTTP/gRPC | `POST /send_order_confirmation` |
| checkout | shipping | gRPC | `ShipOrder` |
| Services | flagd | gRPC | `ResolveBoolean`, `ResolveString`, etc. |
| Services | otel-collector | gRPC/HTTP | OTLP Export |

### Asynchronous (Event-Driven via Kafka)

| Producer | Topic | Consumers |
|---|---|---|
| checkout | `orders` | accounting, fraud-detection |

---

## Notes

- **Line numbers are not verified** — source file scanning was limited; use the File Path column to locate endpoints directly. gRPC method definitions are in `pb/demo.proto`.
- **`product-reviews`** is a Python gRPC service (`product_reviews_server.py`); exact method names should be verified from `src/product-reviews/demo_pb2_grpc.py`.
- **Shipping** implements the `ShippingService` gRPC interface (`GetQuote` and `ShipOrder`) in Rust; the `quote` PHP service may also handle quoting depending on configuration.
- **`frontend-proxy`** serves as the sole external ingress; all external security hardening should be applied at this layer (authentication, rate limiting, CORS).
- The **browser SDK** (frontend) uses both the `/otlp-http/` relay through Envoy and the `/api/data-collection` Next.js relay — these are two separate code paths for browser telemetry.