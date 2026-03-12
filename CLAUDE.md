# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Project Overview

This is the **OpenTelemetry Astronomy Shop Demo** - a polyglot
microservices e-commerce application showcasing OpenTelemetry
instrumentation across multiple programming languages. It serves as a
realistic example for demonstrating distributed tracing, metrics, and
logging.

## Common Commands

### Running the Demo

```bash
make start              # Start all services
make start-minimal      # Start minimal set of services
make stop               # Stop all services
```

### Building

```bash
make build              # Build all Docker images
make redeploy service=<name>  # Rebuild and restart a single service
```

### Testing

```bash
make run-tests          # Run all tests (frontend + trace-based)
make run-tracetesting   # Run trace-based tests only
make run-tracetesting SERVICES_TO_TEST="ad payment"
```

### Linting & Validation

```bash
make check              # Run all checks
make misspell           # Check spelling in markdown files
make markdownlint       # Lint markdown files
make checklicense       # Check license headers
```

### Protobuf Generation

```bash
make generate-protobuf         # Generate protobuf code
make docker-generate-protobuf  # Generate protobuf code via Docker
make clean                     # Remove generated protobuf files
```

## Architecture

### Service Communication

- **gRPC**: Primary protocol for inter-service communication
  (defined in `pb/demo.proto`)
- **HTTP/REST**: Used by frontend, email service, and
  external-facing endpoints
- **Kafka**: Async messaging for checkout to
  accounting/fraud-detection flow
- **Envoy**: Frontend proxy handling routing to all services

### Microservices by Language

| Language             | Services                                     |
|----------------------|----------------------------------------------|
| **Go**               | checkout, product-catalog                    |
| **Java**             | ad, fraud-detection (with OTel Java agent)   |
| **.NET/C#**          | accounting, cart                             |
| **Python**           | recommendation, product-reviews, load-gen    |
| **TypeScript**       | frontend (Next.js), payment                  |
| **Ruby**             | email                                        |
| **PHP**              | quote                                        |
| **C++**              | currency                                     |
| **Rust**             | shipping                                     |
| **Elixir**           | flagd-ui                                     |

### Key Infrastructure Components

- **OpenTelemetry Collector**: Central telemetry pipeline
  (`src/otel-collector/`)
- **Jaeger**: Distributed tracing backend
- **Grafana**: Dashboards and visualization
- **Prometheus**: Metrics storage
- **Flagd**: Feature flags service (`src/flagd/demo.flagd.json`)
- **Kafka**: Event streaming for order processing
- **Valkey**: Cart session storage (Redis-compatible)
- **PostgreSQL**: Persistent storage for accounting

### Directory Structure

```text
src/
  <service>/            # Each microservice has its own directory
    Dockerfile          # Build definition
    README.md           # Service-specific docs
pb/
  demo.proto            # Shared protobuf definitions
test/
  tracetesting/         # Trace-based test definitions
```

## Configuration

- **Environment variables**: Defined in `.env` (base) and
  `.env.override` (local customizations)
- **Docker Compose**: Main orchestration in `docker-compose.yml`
- **Feature flags**: Configured in `src/flagd/demo.flagd.json`

**Note:** Do not commit changes to `.env.override` - it is for local
customizations only.

## Development Workflow

1. Make code changes to a service in `src/<service>/`
2. Rebuild and restart only that service:
   `make redeploy service=<name>`
3. View traces in Jaeger and logs via
   `docker logs <container_name>`
4. For protobuf changes, update `pb/demo.proto` then run
   `make docker-generate-protobuf`

## Git Conventions

All commits must be signed off using the `-s` flag:

```bash
git commit -s -m "Your commit message"
```

This adds a `Signed-off-by` line to the commit message, certifying
that you have the right to submit the code under the project's
license (Developer Certificate of Origin).

## PromQL Conventions

### Prefer `info()` over Resource Attribute Promotion

When writing PromQL queries that need to filter or group by
OpenTelemetry resource attributes (e.g., `service_name`,
`deployment_environment_name`), prefer using the experimental
`info()` function over resource attribute promotion in the collector.

**Pattern:**

```promql
# Preferred: Use info() with data-label-selector
sum by (service_name) (
  info(
    rate(http_server_request_duration_seconds_count
      [$__rate_interval]),
    {deployment_environment_name=~"$env",
     service_name="$service"})
)

# Avoid: Resource attributes promoted directly onto metrics
sum by (service_name) (
  rate(http_server_request_duration_seconds_count{
    deployment_environment_name=~"$env",
    service_name="$service"
  }[$__rate_interval])
)
```

**Why:**

- Reduces metric cardinality in Prometheus
- Resource attributes are stored once in `target_info`
  rather than on every metric
- The `info()` function joins metrics with `target_info`
  at query time

**Note:** Requires Prometheus with
`--enable-feature=promql-experimental-functions`.
