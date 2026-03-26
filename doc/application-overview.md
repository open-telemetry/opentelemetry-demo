# Astronomy Shop – System Overview

> **Project:** OpenTelemetry Demo (`opentelemetry-demo`)  
> **Purpose:** A fully instrumented, polyglot microservices e-commerce application for an astronomy/telescope shop, used as the official reference implementation for OpenTelemetry.

---

## 1. System Overview

The Astronomy Shop is a cloud-native, microservices-based e-commerce platform built entirely to demonstrate OpenTelemetry instrumentation across every major programming language and framework. It simulates a real-world online shop selling telescopes, cameras, and astronomy accessories.

Every service is instrumented with the OpenTelemetry SDK for its language and ships traces, metrics, and logs to a central OpenTelemetry Collector, which fans out to Jaeger (traces), Prometheus (metrics), OpenSearch (logs), and Grafana (dashboards).

The system is deployable via **Docker Compose** (local development) or **Kubernetes** (production-like).

---

## 2. Business Purpose

| Capability | Description |
|---|---|
| **Product browsing** | Browse telescope/astronomy product catalogue with images and recommendations |
| **Shopping cart** | Add items to a persistent cart backed by Valkey (Redis-compatible) |
| **Checkout & payment** | End-to-end checkout flow with currency conversion and credit card processing |
| **Order fulfilment** | Shipping quote calculation and order confirmation via email |
| **Fraud detection** | Real-time transaction fraud analysis via Kafka event stream |
| **Recommendations** | AI-assisted product recommendations |
| **LLM assistant** | Natural language product Q&A powered by an LLM |
| **Feature flags** | Runtime fault injection via FlagD for chaos/resilience testing |
| **Observability** | Full distributed tracing, metrics, and structured logging across all services |

---

## 3. Technology Stack

| Category | Technologies |
|---|---|
| **Languages** | Go, Java, Kotlin, C#/.NET, C++, Node.js, Python, Ruby, PHP, TypeScript, Rust |
| **Frontend** | Next.js 14 (React/TypeScript), React Native (mobile) |
| **API Gateway** | Envoy Proxy |
| **Messaging** | Apache Kafka |
| **Databases** | PostgreSQL 17, Valkey 9 (Redis-compatible) |
| **Observability** | OpenTelemetry Collector, Jaeger, Prometheus, OpenSearch, Grafana |
| **Feature Flags** | FlagD (OpenFeature) |
| **Load Testing** | Locust (Python) |
| **Container Runtime** | Docker / Docker Compose, Kubernetes |
| **OTel SDK versions** | Java agent v2.25, OTel Collector Contrib v0.146.1 |

---

## 4. Service Inventory

### 4.1 Core Application Services

| Service | Language / Runtime | Port | Communication | Dockerfile |
|---|---|---|---|---|
| **frontend** | TypeScript / Next.js 14 | 8080 | HTTP REST (BFF) | `src/frontend/Dockerfile` |
| **frontend-proxy** | Envoy 1.x | 8080 (ext) | HTTP reverse proxy | `src/frontend-proxy/Dockerfile` |
| **ad** | Java 21 / Spring Boot | 9555 | gRPC | `src/ad/Dockerfile` |
| **cart** | C# / .NET 8 | 7070 | gRPC | `src/cart/src/Dockerfile` |
| **checkout** | Go | 5050 | gRPC | `src/checkout/Dockerfile` |
| **currency** | C++ 17 | 7001 | gRPC | `src/currency/Dockerfile` |
| **email** | Ruby / Sinatra | 6060 | HTTP | `src/email/Dockerfile` |
| **fraud-detection** | Kotlin / JVM | — | Kafka consumer | `src/fraud-detection/Dockerfile` |
| **payment** | Node.js | 50051 | gRPC | `src/payment/Dockerfile` |
| **product-catalog** | Go | 3550 | gRPC | `src/product-catalog/Dockerfile` |
| **product-reviews** | — | 3551 | gRPC/HTTP | — |
| **quote** | PHP | 8090 | HTTP | `src/quote/` |
| **recommendation** | Python | 9001 | gRPC | `src/recommendation/` |
| **shipping** | Rust | 50050 | HTTP | `src/shipping/` |
| **accounting** | C# / .NET 8 | — | Kafka consumer | `src/accounting/Dockerfile` |
| **image-provider** | nginx | 8081 | HTTP (static) | `src/image-provider/Dockerfile` |
| **llm** | Python | 8000 | HTTP (OpenAI-compatible) | `src/llm/Dockerfile` |

### 4.2 Platform / Infrastructure Services

| Service | Technology | Port | Purpose |
|---|---|---|---|
| **kafka** | Apache Kafka | 9092 | Async event streaming (orders, fraud) |
| **postgresql** | PostgreSQL 17 | 5432 | Product/order data persistence |
| **valkey-cart** | Valkey 9 (Redis) | 6379 | Cart session storage |
| **flagd** | FlagD (OpenFeature) | 8013 / 8016 | Feature flag evaluation |
| **flagd-ui** | TypeScript / Next.js | 4000 | Feature flag management UI |
| **load-generator** | Python / Locust | 8089 | Synthetic traffic generation |
| **react-native-app** | React Native | — | Mobile app client |

### 4.3 Observability Services

| Service | Technology | Port | Role |
|---|---|---|---|
| **otel-collector** | OTel Collector Contrib v0.146.1 | 4317 (gRPC), 4318 (HTTP) | Telemetry pipeline hub |
| **jaeger** | Jaeger v2.14 | 16686 (UI), 4317 (OTLP) | Distributed trace storage & UI |
| **prometheus** | Prometheus v3.9 | 9090 | Metrics time-series DB |
| **opensearch** | OpenSearch 3.5 | 9200 | Log storage & search |
| **opensearch-dashboards** | OpenSearch Dashboards | 5601 | Log visualisation |
| **grafana** | Grafana 12 | 3000 | Unified observability dashboards |

---

## 5. Service Groupings

### 5.1 Customer-Facing (Synchronous Request Path)

```
Browser → frontend-proxy (Envoy :8080)
              → frontend (Next.js)
                    → product-catalog (gRPC)
                    → cart (gRPC)
                    → checkout (gRPC)
                    → recommendation (gRPC)
                    → ad (gRPC)
                    → currency (gRPC)
                    → shipping (HTTP)
                    → llm (HTTP)
```

### 5.2 Order Fulfilment (Asynchronous Event Path)

```
checkout → Kafka topic: orders
    → accounting (consumer, C#/.NET)
    → fraud-detection (consumer, Kotlin)
checkout → email (HTTP) [confirmation]
```

### 5.3 Infrastructure Dependencies

```
cart ──────────────────→ valkey-cart (Valkey/Redis)
product-catalog ───────→ postgresql
checkout ──────────────→ postgresql
```

### 5.4 Observability Pipeline

```
All services ──OTLP gRPC/HTTP──→ otel-collector
                                      │── traces ──→ jaeger
                                      │── metrics ──→ prometheus
                                      └── logs ─────→ opensearch
jaeger, prometheus, opensearch ───────────────────→ grafana
```

---

## 6. System Architecture Diagram

```mermaid
flowchart TD
    subgraph Clients["Clients"]
        Browser["Web Browser"]
        Mobile["React Native App"]
        LoadGen["Load Generator<br/>Locust :8089"]
    end

    subgraph Gateway["API Gateway"]
        Envoy["Envoy Proxy<br/>frontend-proxy :8080"]
    end

    subgraph Frontend["Frontend"]
        FE["Next.js Frontend<br/>:8080"]
    end

    subgraph CoreServices["Core Business Services"]
        PC["product-catalog<br/>Go :3550"]
        CART["cart<br/>C# :7070"]
        CO["checkout<br/>Go :5050"]
        CUR["currency<br/>C++ :7001"]
        PAY["payment<br/>Node.js :50051"]
        SHIP["shipping<br/>Rust :50050"]
        REC["recommendation<br/>Python :9001"]
        AD["ad<br/>Java :9555"]
        QUO["quote<br/>PHP :8090"]
        EMAIL["email<br/>Ruby :6060"]
        PR["product-reviews<br/>:3551"]
        LLM["llm<br/>Python :8000"]
        IMG["image-provider<br/>nginx :8081"]
    end

    subgraph AsyncServices["Async / Event-Driven Services"]
        KAFKA["Apache Kafka :9092"]
        ACC["accounting<br/>C# (consumer)"]
        FRAUD["fraud-detection<br/>Kotlin (consumer)"]
    end

    subgraph DataStores["Data Stores"]
        PG["PostgreSQL :5432"]
        VALKEY["Valkey/Redis :6379"]
    end

    subgraph FeatureFlags["Feature Flags"]
        FLAGD["FlagD :8013"]
        FLAGDUI["FlagD UI<br/>Next.js :4000"]
    end

    subgraph Observability["Observability Stack"]
        OTELCOL["OTel Collector<br/>gRPC :4317 / HTTP :4318"]
        JAEGER["Jaeger :16686"]
        PROM["Prometheus :9090"]
        OS["OpenSearch :9200"]
        GRAFANA["Grafana :3000"]
    end

    %% Client → Gateway
    Browser & Mobile & LoadGen --> Envoy

    %% Gateway routing
    Envoy --> FE
    Envoy -- "/otlp-http/" --> OTELCOL
    Envoy -- "/jaeger/ui/" --> JAEGER
    Envoy -- "/grafana/" --> GRAFANA
    Envoy -- "/prometheus/" --> PROM

    %% Frontend → backend services
    FE --> PC & CART & CO & REC & AD & CUR & SHIP & LLM & PR

    %% Checkout dependencies
    CO --> CUR & PAY & QUO & EMAIL & CART

    %% Async order flow
    CO -- "order event" --> KAFKA
    KAFKA --> ACC & FRAUD

    %% Data store access
    CART --> VALKEY
    PC --> PG
    CO --> PG

    %% Feature flags used by services
    FE & CO & REC & AD & FRAUD -.-> FLAGD

    %% All services → OTel Collector
    FE & PC & CART & CO & CUR & PAY & SHIP & REC & AD & EMAIL & FRAUD & ACC & QUO -.->|"OTLP traces/metrics/logs"| OTELCOL

    %% OTel pipeline fan-out
    OTELCOL -->|traces| JAEGER
    OTELCOL -->|metrics| PROM
    OTELCOL -->|logs| OS

    %% Grafana data sources
    JAEGER & PROM & OS -.->|"data source"| GRAFANA

    %% FlagD UI manages FlagD
    FLAGDUI --> FLAGD
```

---

## 7. Component Architecture Diagrams

### 7.1 Frontend Request Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant E as Envoy Proxy
    participant F as Frontend (Next.js)
    participant PC as product-catalog
    participant CART as cart
    participant REC as recommendation
    participant AD as ad
    participant CUR as currency

    B->>E: GET / (HTTP :8080)
    E->>F: proxy to frontend:8080
    F->>PC: ListProducts (gRPC)
    F->>REC: ListRecommendations (gRPC)
    F->>AD: GetAds (gRPC)
    F->>CUR: GetSupportedCurrencies (gRPC)
    F-->>B: HTML page with products

    B->>E: POST /api/cart
    E->>F: proxy
    F->>CART: AddItem (gRPC)
    CART-->>F: cart updated
    F-->>B: 200 OK
```

### 7.2 Checkout Flow

```mermaid
sequenceDiagram
    participant F as Frontend
    participant CO as checkout (Go)
    participant CUR as currency (C++)
    participant CART as cart (C#)
    participant QUO as quote (PHP)
    participant PAY as payment (Node.js)
    participant EMAIL as email (Ruby)
    participant K as Kafka
    participant ACC as accounting (C#)
    participant FRAUD as fraud-detection (Kotlin)

    F->>CO: PlaceOrder (gRPC)
    CO->>CUR: Convert prices (gRPC)
    CO->>CART: GetCart (gRPC)
    CO->>QUO: GetQuote (HTTP)
    CO->>PAY: Charge (gRPC)
    PAY-->>CO: transaction_id
    CO->>EMAIL: SendConfirmation (HTTP)
    CO->>K: publish OrderPlaced
    CO->>CART: EmptyCart (gRPC)
    CO-->>F: order_id
    K-->>ACC: consume (persist ledger)
    K-->>FRAUD: consume (analyse transaction)
```

### 7.3 Observability Data Flow

```mermaid
flowchart LR
    subgraph Services["Application Services"]
        S1["Frontend / BFF"]
        S2["Backend Services<br/>(Go, Java, .NET, C++,<br/>Node.js, Python, Ruby, Rust)"]
        S3["Kafka Consumers<br/>(accounting, fraud-detection)"]
    end

    subgraph Collector["OTel Collector (otel-collector)"]
        RCV[/"Receivers<br/>OTLP gRPC :4317<br/>OTLP HTTP :4318<br/>+ infra receivers"/]
        PROC["Processors<br/>resourcedetection<br/>memory_limiter<br/>transform/sanitize_spans"]
        SM[/"spanmetrics<br/>connector"/]
        EXP["Exporters"]
    end

    subgraph Backends["Backends"]
        J["Jaeger<br/>(traces)"]
        P["Prometheus<br/>(metrics)"]
        O["OpenSearch<br/>(logs)"]
        G["Grafana<br/>(dashboards)"]
    end

    S1 & S2 & S3 -- "OTLP gRPC/HTTP" --> RCV
    RCV --> PROC
    PROC --> SM
    PROC -->|traces| EXP
    SM -->|span metrics| PROC
    PROC -->|metrics| EXP
    PROC -->|logs| EXP

    EXP -->|otlp_grpc/jaeger| J
    EXP -->|otlp_http/prometheus| P
    EXP -->|opensearch exporter| O
    J & P & O --> G
```

### 7.4 Feature Flag & Fault Injection

```mermaid
flowchart TD
    subgraph UI["FlagD UI (Next.js :4000)"]
        FUI["Flag Management Interface"]
    end

    subgraph FlagD["FlagD :8013"]
        FF["demo.flagd.json<br/>(flag definitions)"]
    end

    subgraph Consumers["Services using flags"]
        FE2["frontend"]
        CO2["checkout"]
        REC2["recommendation"]
        AD2["ad"]
        FRAUD2["fraud-detection"]
    end

    FUI -->|"update flags"| FlagD
    FlagD -->|"OpenFeature SDK"| FE2 & CO2 & REC2 & AD2 & FRAUD2

    FE2 -.->|"productCatalogFailure<br/>cartServiceFailure"| FaultA["Simulated errors<br/>in cart/catalog"]
    CO2 -.->|"paymentServiceFailure"| FaultB["Payment failure injection"]
    FRAUD2 -.->|"fraudDetectionScenario"| FaultC["Fraud risk adjustment"]
```

---

## 8. Inter-Service Communication Summary

| From | To | Protocol | Purpose |
|---|---|---|---|
| frontend | product-catalog | gRPC | List/get products |
| frontend | cart | gRPC | Cart CRUD |
| frontend | checkout | gRPC | Place order |
| frontend | recommendation | gRPC | Get recommendations |
| frontend | ad | gRPC | Get contextual ads |
| frontend | currency | gRPC | Currency conversion |
| frontend | shipping | HTTP | Get shipping cost |
| frontend | llm | HTTP | Product Q&A |
| frontend | product-reviews | gRPC/HTTP | Product reviews |
| checkout | cart | gRPC | Read and empty cart |
| checkout | currency | gRPC | Price conversion |
| checkout | payment | gRPC | Charge card |
| checkout | quote | HTTP | Shipping quote |
| checkout | email | HTTP | Order confirmation |
| checkout | Kafka | Produce | Order placed event |
| Kafka | accounting | Consume | Financial ledger |
| Kafka | fraud-detection | Consume | Fraud analysis |
| cart | Valkey | Redis protocol | Session storage |
| product-catalog | PostgreSQL | SQL | Product data |
| checkout | PostgreSQL | SQL | Order data |
| All services | otel-collector | OTLP gRPC/HTTP | Telemetry export |

---

## 9. Deployment

### Docker Compose (Local)

```bash
# Start all services
docker compose up --build

# Access points
# Web UI:      http://localhost:8080
# Grafana:     http://localhost:8080/grafana/       (admin/admin)
# Jaeger:      http://localhost:8080/jaeger/ui/
# Prometheus:  http://localhost:8080/prometheus/
# FlagD UI:    http://localhost:8080/flagd-ui/
# Load Gen:    http://localhost:8089
```

Key Docker Compose files:
- `docker-compose.yml` — full stack
- `docker-compose.minimal.yml` — core services only
- `docker-compose-tests.yml` — trace-based testing

### Kubernetes

```bash
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

Services are exposed via Ingress. The OTel Collector ClusterIP service is named `opentelemetry-demo-otelcol`.

---

## 10. References

| Resource | Location |
|---|---|
| Main README | `README.md` |
| OTel Collector config | `src/otel-collector/otelcol-config.yml` |
| Environment variables | `.env` |
| Feature flag definitions | `src/flagd/demo.flagd.json` |
| Kubernetes manifest | `kubernetes/opentelemetry-demo.yaml` |
| Envoy proxy config | `src/frontend-proxy/envoy.tmpl.yaml` |
| Prometheus config | `src/prometheus/prometheus-config.yaml` |
| Grafana provisioning | `src/grafana/provisioning/` |
| Load generator script | `src/load-generator/locustfile.py` |
| Proto definitions | `pb/demo.proto` |
| OTEL setup guide | `doc/otel_setup.md` |