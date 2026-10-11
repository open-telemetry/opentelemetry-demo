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
   (`demo.ad.requests`) is created via `GlobalOpenTelemetry.getMeter(...)`
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

**Recommendation**: this is a *transitional* pattern. Prefer the
OpenTelemetry SDK for new custom metrics, and migrate existing
Prometheus-client metrics to it - incremental migration as you touch
the surrounding code has proven successful in practice, but a focused
refactor works too; what matters is that the migration happens.

## Metric cardinality overflow scenario

The `adMetricCardinalityOverflow` feature flag adds a fresh UUID in
`demo.ad.request_id` to each `demo.ad.requests` measurement. It is off by default.
This deliberately demonstrates an unsafe metric attribute: each request creates
another attribute combination until the Java SDK's cardinality limit is reached.
The SDK then aggregates additional combinations into a point marked
`otel.metric.overflow=true`, without the original measurement attributes.

### Try it locally

From the repository root:

```sh
make build service=ad
make start
```

1. Open the [feature flag UI](http://localhost:8080/feature) and set
   `adMetricCardinalityOverflow` to `on`.
2. Let the load generator run, or, with [grpcurl](https://github.com/fullstorydev/grpcurl)
   installed on your host, send this burst from the repository root to exceed the
   default limit of 2,000 combinations quickly. Leave `adFailure` off during the burst.

   ```sh
   ad_port=$(docker port ad 9555/tcp | head -n 1 | awk -F: '{print $NF}')
   for i in $(seq 1 2500); do
     grpcurl -plaintext -import-path ./pb -proto demo.proto -d '{}' \
       "localhost:${ad_port}" oteldemo.AdService/GetAds >/dev/null || break
   done
   ```

3. Allow one metric export interval (normally 60 seconds), then open the
   [Self-Observability dashboard](http://localhost:8080/grafana/d/self-observability).
   Select service `ad` and expand **Metric cardinality overflow** at the bottom.
   **Services with overflow observed** should include `ad`, and the table should
   list the Prometheus name of `demo.ad.requests` with its service instance.
4. To inspect the data directly in Prometheus, query
   `{otel_metric_overflow="true",service_name="ad"}`. Normal series retain
   request and response types; the overflow series loses those attributes.
   The counter's total still includes the overflowed requests.

### Turn it off and reset

Set `adMetricCardinalityOverflow` back to `off`. This stops adding unique IDs,
but does not clear the SDK's aggregation state. With the demo's default cumulative
metrics, the overflow point can continue to be exported with an unchanged value.
The dashboard reports overflow **observed in the selected time range**, not
necessarily new overflow occurring now.

To reset the SDK state, turn the flag off and run `docker restart ad`. Historical
overflow remains in Prometheus; choose a dashboard time range starting after the
restart to check the clean state. Normal attribute combinations first seen only
after the limit was reached can also overflow until the SDK state is reset.

See [Metric cardinality limits in OpenTelemetry](https://opentelemetry.io/blog/2026/cardinality-limits-in-opentelemetry/)
for the impact on attribute-filtered queries and guidance on real instrumentation.
