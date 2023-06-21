# Accounting Service

This service consumes new orders from a Kafka topic.

## Local Build

To build the service binary, run:

```sh
go build -o /go/bin/accountingservice/
```

## Docker Build

From the root directory, run:

```sh
docker compose build accountingservice
```

## Regenerate protos

> **Note**
> [`protoc`](https://grpc.io/docs/protoc-installation/) is required.

To regenerate gRPC code run:

```sh
go generate
```

## Bump dependencies

To bump all dependencies run:

```sh
go get -u -t ./...
go mod tidy
```
