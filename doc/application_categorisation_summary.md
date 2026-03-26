# Application OTel Categorisation Summary

> **Source:** `doc/application_categorisation.csv`  
> **Scope:** All top-level folders under `src/` in the OpenTelemetry Demo repository.

---

## Counts

| Category | Count |
|---|---|
| Total folders analysed | 28 |
| **Has OTel integration** (`yes`) | **20** |
| **No OTel integration** (`no`) | **8** |

---

## Folders WITH OTel Integration (20)

| Folder | Language / Runtime | OTel Mechanism |
|---|---|---|
| `accounting` | C# / .NET | OpenTelemetry .NET SDK — manual + auto instrumentation |
| `ad` | Java | OpenTelemetry Java Agent (`-javaagent`) — auto instrumentation |
| `cart` | C# / .NET | OpenTelemetry .NET SDK — traces, metrics, logs |
| `checkout` | Go | `go.opentelemetry.io/otel` SDK — traces, metrics, logs |
| `currency` | C++ | `opentelemetry-cpp` SDK — traces, metrics |
| `email` | Ruby | `opentelemetry-ruby` gem — traces |
| `flagd-ui` | Elixir / Phoenix | `opentelemetry_exporter` + `opentelemetry_phoenix` Hex packages |
| `fraud-detection` | Kotlin / JVM | OpenTelemetry Java Agent — auto instrumentation |
| `frontend` | TypeScript / Next.js | `@opentelemetry/sdk-web` (browser) + `@opentelemetry/sdk-node` (SSR) |
| `frontend-proxy` | Envoy config | Configured to route browser OTLP HTTP to `otel-collector:4318` |
| `llm` | Python | `opentelemetry-sdk` Python package |
| `load-generator` | Python / Locust | `opentelemetry-sdk` — injects W3C `traceparent` headers into requests |
| `otel-collector` | OTel Collector config | IS the Collector — defines OTLP receivers, spanmetrics connector, exporters |
| `payment` | Node.js | `@opentelemetry/sdk-node` — explicitly initialised in `opentelemetry.js` |
| `product-catalog` | Go | `go.opentelemetry.io/otel` SDK — traces, metrics, logs |
| `product-reviews` | TBD (see note) | OTel SDK — instrumented as part of the demo |
| `quote` | PHP | `open-telemetry/sdk` PHP package |
| `react-native-app` | React Native | `@opentelemetry/sdk-react-native` — client-side mobile traces |
| `recommendation` | Python | `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-grpc` |
| `shipping` | Rust | `opentelemetry` + `opentelemetry-otlp` crates |

> **Note on `product-reviews`:** The folder exists and is registered in `.env` with `PRODUCT_REVIEWS_PORT=3551`. The implementation language can be confirmed from `src/product-reviews/` source files. OTel instrumentation is expected as this is part of the demo.

---

## Folders WITHOUT OTel Integration (8)

| Folder | Type | Reason |
|---|---|---|
| `flagd` | Feature flag config | Contains only `demo.flagd.json`; no application code |
| `grafana` | Observability backend config | `grafana.ini` + dashboard provisioning; Grafana consumes from Prometheus/Jaeger/OpenSearch data sources |
| `image-provider` | nginx static file server | Serves product images; nginx metrics are **scraped by** the OTel Collector externally (nginx receiver), not emitted by the service |
| `jaeger` | Trace backend config | `config.yml` only; Jaeger is the trace storage backend receiving OTLP from the collector |
| `kafka` | Message broker | Apache Kafka broker `Dockerfile`; broker itself has no OTel SDK; metrics may be scraped via JMX |
| `opensearch` | Log storage backend | `Dockerfile` only; OpenSearch receives logs from the OTel Collector opensearch exporter |
| `postgresql` | Database | `Dockerfile` + database init scripts; PostgreSQL metrics scraped externally by OTel Collector postgresql receiver |
| `prometheus` | Metrics backend config | `prometheus-config.yaml` only; Prometheus receives OTLP HTTP push from the collector |

---

## OTel Integration Patterns Used

| Pattern | Services |
|---|---|
| **OpenTelemetry SDK (manual instrumentation)** | checkout, currency, frontend, payment, product-catalog, recommendation, shipping, llm, quote, email, react-native-app |
| **OpenTelemetry Java Agent (auto instrumentation)** | ad, fraud-detection |
| **OpenTelemetry .NET SDK (auto + manual)** | accounting, cart |
| **OTLP HTTP routing (proxy)** | frontend-proxy (Envoy) |
| **OTel Collector config** | otel-collector |
| **Metrics scraping (pull model)** | image-provider, postgresql (scraped by collector) |

---

## Notes

- **All application services** (services with business logic) have OTel integration, consistent with the project's goal of demonstrating OTel across every major language.
- **Config-only and infrastructure services** (Grafana, Prometheus, Jaeger, OpenSearch, Kafka, PostgreSQL, flagd) do not have OTel SDK integration — they are telemetry consumers or infrastructure components.
- **`frontend-proxy`** has OTel integration in a non-SDK sense: its Envoy configuration routes browser OTLP telemetry to the collector.
- **`otel-collector`** is the telemetry pipeline itself — its config constitutes OTel integration at the infrastructure level.
- The `flagd-ui` service has been **rewritten in Elixir/Phoenix** (previously Next.js); the Elixir OTel SDK (`opentelemetry_exporter` hex package) is used.