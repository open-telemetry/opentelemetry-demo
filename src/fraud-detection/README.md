# Fraud Detection Service

This service receives new orders by a Kafka topic and returns cases which are
suspected of fraud.

## Business metrics

The existing order consumer records `demo.business.orders` (unit `{order}`) and
`demo.business.sales` (unit `{currency}`) through the OpenTelemetry API. The Java
agent supplies the SDK and exports the metrics. Sales multiply product prices by
quantities, exclude shipping, and use a `currency` attribute to keep currencies
separate.

Use `increase()` over a one-hour window for hourly order and sales totals,
grouping sales by currency. Counters reset on restart, and replayed Kafka
messages can count an order again. The metrics follow the existing consumer, so
`kafkaConsumerDead` pauses them and `kafkaQueueProblems` delays them.

## Local Build

To build the protos and the service binary, run from the repo root:

```sh
cp -r ../../pb/ src/main/proto/
./gradlew shadowJar
```

## Docker Build

To build using Docker run from the repo root:

```sh
docker build -f ./src/fraud-detection/Dockerfile .
```
