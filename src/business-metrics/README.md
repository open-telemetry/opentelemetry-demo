# Business Metrics

This optional Java service reads protobuf `OrderResult` messages from the
`orders` Kafka topic. Its own consumer group receives orders independently of
accounting and fraud detection. Removing it does not affect checkout.

The application depends on the OpenTelemetry API only. Its image contains no
SDK, exporter, or Java agent. Without injected instrumentation it processes
orders and writes Java logging messages, with no telemetry export.

## Metrics

| Metric | Unit | Meaning |
| --- | --- | --- |
| `demo.business.orders` | `{order}` | Processed orders |
| `demo.business.sales` | `{currency}` | Product prices multiplied by quantities, excluding shipping |

Sales have a `currency` attribute, so different currencies are never added
together. Apply a rate over one hour to the orders counter for orders/hour,
or an increase over one hour to sales for sales/hour, grouped by currency.

Offsets are committed after processing each batch. Delivery is at least once,
so replay after a crash can count an order again. Counters reset when the
process restarts. These are demonstration metrics, not a financial ledger.
Malformed messages are logged and skipped. Kafka tombstones are ignored.

## Docker Compose

The service is excluded from the default demo. To build and run it without
instrumentation:

```sh
docker compose -f compose.yaml -f compose.full.yaml -f compose.business-metrics.yaml up --build
```

`KAFKA_ADDR` and `KAFKA_TOPIC` use the same settings as the other order consumers.
No other service depends on business-metrics.

## Operator injection

Install the [OpenTelemetry Operator](https://opentelemetry.io/docs/platforms/kubernetes/operator/)
and create an
[Instrumentation resource](https://opentelemetry.io/docs/platforms/kubernetes/operator/automatic/)
in the demo namespace, with its exporter endpoint pointing to your Collector.
The deployment's pod annotation asks the operator to inject Java instrumentation.
If more than one Instrumentation resource exists, replace `true` with its name.

Build the image, load it into your local cluster, and apply the optional deployment
in the same namespace as the demo and Instrumentation resource:

```sh
docker build -f src/business-metrics/Dockerfile -t otel-demo-business-metrics:local .
kubectl apply -n <demo-namespace> -f src/business-metrics/kubernetes.yaml
```

For a remote cluster, push the image to your registry and change the deployment's
image reference. Set `KAFKA_ADDR` to your demo's Kafka service name, including any
Helm release prefix. The injected agent supplies the SDK, exports the custom
metrics, and instruments Kafka and Java logging. No Kubernetes Service or inbound
port is needed.

## Tests

From the repository root, using the recommendation service's Gradle wrapper:

```sh
src/recommendation/gradlew -p src/business-metrics test
```
