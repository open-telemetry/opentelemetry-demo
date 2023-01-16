# Demo Architecture

**OpenTelemetry Demo** is composed of microservices written in different programming
languages that talk to each other over gRPC and HTTP; and a load generator which
uses [Locust](https://locust.io/) to fake user traffic.

```mermaid
graph TD
subgraph Service Diagram
accountingservice(Accounting Service):::golang
adservice(Ad Service):::java
cache[(Cache<br/>&#40redis&#41)]
cartservice(Cart Service):::dotnet
checkoutservice(Checkout Service):::golang
currencyservice(Currency Service):::cpp
emailservice(Email Service):::ruby
frauddetectionservice(Fraud Detection Service):::kotlin
frontend(Frontend):::typescript
frontendproxy(Frontend Proxy <br/>&#40Envoy&#41):::cpp
loadgenerator([Load Generator]):::python
paymentservice(Payment Service):::javascript
productcatalogservice(Product Catalog Service):::golang
quoteservice(Quote Service):::php
recommendationservice(Recommendation Service):::python
shippingservice(Shipping Service):::rust
featureflagservice(Feature Flag Service):::erlang
featureflagstore[(Feature Flag Store<br/>&#40PostgreSQL DB&#41)]
queue[(queue<br/>&#40Kafka&#41)]

Internet -->|HTTP| frontendproxy
frontendproxy -->|HTTP| frontend
frontendproxy -->|HTTP| featureflagservice
loadgenerator -->|HTTP| frontend

accountingservice -->|TCP| queue

checkoutservice --->|gRPC| cartservice --> cache
checkoutservice --->|gRPC| productcatalogservice
checkoutservice --->|gRPC| currencyservice
checkoutservice --->|HTTP| emailservice
checkoutservice --->|gRPC| paymentservice
checkoutservice -->|gRPC| shippingservice
checkoutservice -->|TCP| queue

frontend -->|gRPC| adservice
frontend -->|gRPC| cartservice
frontend -->|gRPC| productcatalogservice
frontend -->|gRPC| checkoutservice
frontend -->|gRPC| currencyservice
frontend -->|gRPC| recommendationservice -->|gRPC| productcatalogservice
frontend -->|gRPC| shippingservice -->|HTTP| quoteservice

frauddetectionservice -->|TCP| queue

productcatalogservice -->|gRPC| featureflagservice

shippingservice -->|gRPC| featureflagservice

featureflagservice --> featureflagstore

end

classDef dotnet fill:#178600,color:white;
classDef cpp fill:#f34b7d,color:white;
classDef erlang fill:#b83998,color:white;
classDef golang fill:#00add8,color:black;
classDef java fill:#b07219,color:white;
classDef javascript fill:#f1e05a,color:black;
classDef kotlin fill:#560ba1,color:white;
classDef php fill:#4f5d95,color:white;
classDef python fill:#3572A5,color:white;
classDef ruby fill:#701516,color:white;
classDef rust fill:#dea584,color:black;
classDef typescript fill:#e98516,color:black;
```

```mermaid
graph TD
subgraph Service Legend
  dotnetsvc(.NET):::dotnet
  cppsvc(C++):::cpp
  erlangsvc(Erlang/Elixir):::erlang
  golangsvc(Go):::golang
  javasvc(Java):::java
  javascriptsvc(JavaScript):::javascript
  kotlinsvc(Kotlin):::kotlin
  phpsvc(PHP):::php
  pythonsvc(Python):::python
  rubysvc(Ruby):::ruby
  rustsvc(Rust):::rust
  typescriptsvc(TypeScript):::typescript
end

classDef dotnet fill:#178600,color:white;
classDef cpp fill:#f34b7d,color:white;
classDef erlang fill:#b83998,color:white;
classDef golang fill:#00add8,color:black;
classDef java fill:#b07219,color:white;
classDef javascript fill:#f1e05a,color:black;
classDef kotlin fill:#560ba1,color:white;
classDef php fill:#4f5d95,color:white;
classDef python fill:#3572A5,color:white;
classDef ruby fill:#701516,color:white;
classDef rust fill:#dea584,color:black;
classDef typescript fill:#e98516,color:black;
```

Follow these links for the current state of
 [metric](https://github.com/open-telemetry/opentelemetry-demo/blob/main/docs/metric_service_features.md)
 and
 [trace](https://github.com/open-telemetry/opentelemetry-demo/blob/main/docs/trace_service_features.md)
 instrumentation of the demo applications.

The collector is configured in
 [otelcol-config.yml](https://github.com/open-telemetry/opentelemetry-demo/blob/main/src/otelcollector/otelcol-config.yml),
 alternative exporters can be configured here.

```mermaid
graph TB
subgraph tdf[Telemetry Data Flow]
    subgraph subgraph_padding [ ]
        style subgraph_padding fill:none,stroke:none;
        %% padding to stop the titles clashing
        subgraph od[Open Telemetry Demo]
        ms(Microservice)
        end

        ms -.->|"OTLP<br/>gRPC"| oc-grpc
        ms -.->|"OTLP<br/>HTTP POST"| oc-http

        subgraph oc[OTel Collector]
            style oc fill:#97aef3,color:black;
            oc-grpc[/"OTLP Receiver<br/>listening on<br/>grpc://localhost:4317/"/]
            oc-http[/"OTLP Receiver<br/>listening on <br/>http://localhost:4318/<br/>https://localhost:4318/"/]
            oc-proc(Processors)
            oc-prom[/"Prometheus Exporter<br/>listening on<br/>http://localhost:9464/"/]
            oc-jag[/"Jaeger Exporter"/]

            oc-grpc --> oc-proc
            oc-http --> oc-proc

            oc-proc --> oc-prom
            oc-proc --> oc-jag
        end

        oc-prom -->|"http://localhost:9464/metrics"| pr-sc
        oc-jag -->|gRPC| ja-col

        subgraph pr[Prometheus]
            style pr fill:#e75128,color:black;
            pr-sc[/"Prometheus Scraper<br/>polling every 5 seconds"/]
            pr-tsdb[(Prometheus TSDB)]
            pr-http[/"Prometheus HTTP<br/>listening on<br/>http://localhost:9090"/]

            pr-sc --> pr-tsdb
            pr-tsdb --> pr-http
        end

        pr-b{{"Browser<br/>Prometheus UI"}}
        pr-http ---->|"http://localhost:9090/graph"| pr-b

        subgraph ja[Jaeger]
            style ja fill:#60d0e4,color:black;
            ja-col[/"Jaeger Collector<br/>listening on<br/>grpc://jaeger:4317/"/]
            ja-db[(Jaeger DB)]
            ja-http[/"Jaeger HTTP<br/>listening on<br/>http://localhost:16686"/]

            ja-col --> ja-db
            ja-db --> ja-http
        end

        subgraph gr[Grafana]
            style gr fill:#f8b91e,color:black;
            gr-srv["Grafana Server"]
            gr-http[/"Grafana HTTP<br/>listening on<br/>http://localhost:3000"/]

            gr-srv --> gr-http
        end

        pr-http --> |"http://localhost:9090/api"| gr-srv
        ja-http --> |"http://localhost:16686/api"| gr-srv

        ja-b{{"Browser<br/>Jaeger UI"}}
        ja-http ---->|"http://localhost:16686/search"| ja-b

        gr-b{{"Browser<br/>Grafana UI"}}
        gr-http -->|"http://localhost:3000/dashboard"| gr-b
    end
end
```

Find the **Protocol Buffer Definitions** in the `/pb/` directory.
