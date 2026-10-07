# Recommendation Service

This service provides recommendations for other products based on the currently
selected product.

It is a Spring Boot 4 application. The gRPC API is served with Spring gRPC, and
the telemetry comes from the OpenTelemetry Java agent, attached in the Docker
image the same way as the ad service.

## Local Build

Requires JDK 21 or newer. The protobuf classes are generated from
`../../pb/demo.proto` as part of the Gradle build:

```sh
./gradlew build
```

## Docker Build

From the root directory, run:

```sh
docker compose build recommendation
```
