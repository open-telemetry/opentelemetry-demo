# Checkout Service

This service provides checkout services for the application.

It also shows how to do compile-time instrumentation of Go applications with
[`otelc`](https://github.com/open-telemetry/opentelemetry-go-compile-instrumentation),
the OpenTelemetry Go compile-time instrumentation tool. The Docker image is built
with `go tool otelc go build` instead of `go build`, so `otelc` instruments gRPC,
HTTP, `log/slog` and Go runtime metrics at compile time and initializes the
OpenTelemetry SDK. The service code contains no SDK setup for these signals.
`otelc` is declared as a `tool` dependency in `go.mod`.

## Local Build

To build the service binary without instrumentation, run:

```sh
go build -o /go/bin/checkout/
```

To build it with compile-time instrumentation, as the Docker image does, run:

```sh
go tool otelc go build -o /go/bin/checkout/
```

## Docker Build

From the root directory, run:

```sh
docker compose build checkout
```

## Regenerate protos

To build the protos, run from the root directory:

```sh
make docker-generate-protobuf
```

## Generate feature flag types

To regenerate the typed feature flag accessors from `flags.json`, run from the
service directory:

```sh
go generate ./...
```

This uses the [OpenFeature CLI](https://github.com/open-feature/cli) to
produce `flags/flags_gen.go`.

## Bump dependencies

To bump all dependencies run:

```sh
go get -u -t ./...
go mod tidy
```
