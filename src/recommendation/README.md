# Recommendation Service

This service provides recommendations for other products based on the currently
selected product.

> [!NOTE]
> This service uses the OpenTelemetry Spring Boot starter so the demo shows a
> second way to instrument Java. It is not the default recommendation. The
> default choice for Spring Boot applications is the OpenTelemetry Java agent,
> which the [ad service](../ad/README.md) uses. The
> [Spring Boot starter](https://opentelemetry.io/docs/zero-code/java/spring-boot-starter/)
> page explains when the starter is the better fit.

It is a Spring Boot 4 application. The gRPC API is served with Spring gRPC, and
the telemetry comes from the OpenTelemetry Spring Boot starter plus the
OpenTelemetry gRPC instrumentation library, so no Java agent is involved.

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
