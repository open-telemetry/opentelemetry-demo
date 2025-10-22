# Accounting Service

This service consumes new orders from a Kafka topic.

## Local Build

To build the service binary, navigate to the root directory of the project and run:

```sh
make generate-protobuf
```

Navigate back to `src/accounting` and execute:

```sh
dotnet build
```

## Docker Build

From the root directory, run:

```sh
docker compose build accounting
```

## Bump dependencies

To bump all dependencies run in Package manager:

```sh
Update-Package -ProjectName Accounting
```
