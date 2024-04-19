# Accounting Service

This service consumes new orders from a Kafka topic.

## Local Build

To build the service binary, run:

```sh
dotnet build
```

## Docker Build

From the root directory, run:

```sh
docker compose build accountingservice
```

## Bump dependencies

To bump all dependencies run in Package manager:

```sh
Update-Package -ProjectName AccountingService
```
