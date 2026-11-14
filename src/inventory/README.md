# Inventory Service

The Inventory service tracks stock levels and reserves stock for orders.
Checkout calls it before charging the card.

Stock is kept in memory. Every product starts with 100 units and is restocked
when a reservation would take it below zero.

It is a Zig based service using manual instrumentation with the
[OpenTelemetry Zig SDK](https://github.com/open-telemetry/opentelemetry-zig).

## Endpoints

| Method | Path       | Description                          |
|--------|------------|--------------------------------------|
| `POST` | `/reserve` | Reserve stock for an order           |
| `GET`  | `/health`  | Liveness probe used by the container |

## Docker Build

To build the inventory service, run the following from the root directory of
opentelemetry-demo:

```sh
docker compose build inventory
```

## Run the service

```sh
docker compose up inventory
```

In order to get traffic into the service you have to deploy the whole
opentelemetry-demo. Please follow the root README to do so.

## Local development

This service requires Zig 0.16.0. See the
[Zig download page](https://ziglang.org/download/) for install instructions.

Build and run from `src/inventory`:

```sh
zig build
INVENTORY_PORT=8070 \
OTEL_SERVICE_NAME=inventory \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
./zig-out/bin/inventory
```

Then send a request:

```sh
curl --location 'http://localhost:8070/reserve' \
--header 'Content-Type: application/json' \
--data '{"order_id":"order-1","items":[{"product_id":"OLJCESPC7Z","quantity":2}]}'
```

## Tests

```sh
zig build test
```

## Environment Variables

| Variable                      | Default | Description                        |
|-------------------------------|---------|------------------------------------|
| `INVENTORY_PORT`              |         | Port the HTTP server listens on    |
| `FLAGD_HOST`                  |         | flagd host for feature flags       |
| `FLAGD_OFREP_PORT`            |         | flagd OFREP port                   |
| `OTEL_SERVICE_NAME`           |         | Service name reported in telemetry |
| `OTEL_EXPORTER_OTLP_ENDPOINT` |         | OTLP endpoint of the collector     |
| `OTEL_EXPORTER_OTLP_PROTOCOL` |         | Must be `http/protobuf`            |

The Zig SDK does not implement an OTLP gRPC exporter, so this service exports
over OTLP HTTP.

## Feature flags

There is no OpenFeature SDK for Zig, so the service evaluates flags through
flagd's [OFREP](https://github.com/open-feature/protocol) endpoint. When
`FLAGD_HOST` or `FLAGD_OFREP_PORT` is unset, or flagd is unreachable, flags
evaluate to off.

| Flag               | Effect                                                    |
|--------------------|-----------------------------------------------------------|
| `inventoryFailure` | `/reserve` returns 503 for orders containing `OLJCESPC7Z` |
