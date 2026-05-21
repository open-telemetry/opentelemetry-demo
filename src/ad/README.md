# Ad Service

The Ad service provides advertisement based on context keys. If no context keys
are provided then it returns random ads.

## Building Locally

The Ad service requires at least JDK 21 to build and uses gradlew to
compile/install/distribute. Gradle wrapper is already part of the source code.
To build Ad Service, run:

```sh
./gradlew installDist
```

It will create an executable script
`src/ad/build/install/oteldemo/bin/Ad`.

To run the Ad Service:

```sh
export AD_PORT=8080
export FEATURE_FLAG_GRPC_SERVICE_ADDR=featureflagservice:50053
./build/install/opentelemetry-demo-ad/bin/Ad
```

### Upgrading Gradle

If you need to upgrade the version of gradle then run

```sh
./gradlew wrapper --gradle-version <new-version>
```

## Building Docker

From the root of `opentelemetry-demo`, run:

```sh
docker build --file ./src/ad/Dockerfile ./
```

## Custom metrics: bridging Prometheus to OpenTelemetry

The Ad service intentionally emits custom metrics in **two different ways**:

1. **OpenTelemetry SDK** (recommended): `adRequestsCounter`
   (`app.ads.ad_requests`) is created via `GlobalOpenTelemetry.getMeter(...)`
   and exported to the OTel Collector over OTLP.
2. **Prometheus client library**: `adsServedCounter`
   (`demo_ad_served_total{category}`) is created with the
   `io.prometheus:prometheus-metrics-core` library and exposed on a separate
   HTTP endpoint (`AD_PROMETHEUS_PORT`, default `9465`). The OTel Collector's
   `prometheus/ad` receiver scrapes this endpoint and forwards the metric
   into the same metrics pipeline.

The Prometheus-client path is included to demonstrate a **common pattern
during OpenTelemetry adoption**: organizations frequently already own a
significant amount of Prometheus instrumentation (in libraries, third-party
exporters, or legacy services) and want to ingest those metrics into an
OpenTelemetry-native pipeline without rewriting everything up front. The
Collector's `prometheus` receiver is the bridge that makes this possible.

**Recommendation**: this is a *transitional* pattern. For new custom
metrics, prefer the OpenTelemetry SDK directly - it gives you a single
SDK, native context propagation (exemplars linked to traces, resource
attributes, baggage), and a single configuration surface. Migrate existing
Prometheus-client metrics to the OTel SDK as you touch the surrounding
code, rather than as a separate, large refactor.
