# Telemetry Documentation Service

This service generates and hosts comprehensive documentation for the
OpenTelemetry Demo's telemetry schema using
[OpenTelemetry Weaver](https://github.com/open-telemetry/weaver),
[MkDocs](https://www.mkdocs.org/), and
[nginx with OpenTelemetry instrumentation](https://github.com/nginxinc/nginx-otel).

## Overview

The telemetry-docs service provides a web-based documentation interface that
documents all custom attributes and metrics used across the OpenTelemetry Demo
application. The documentation is automatically generated from the YAML schema
definitions in the `telemetry-schema/` directory and served as a static site
with full OpenTelemetry tracing.

## Architecture

The service uses a **3-stage Docker build** for optimal performance and observability:

### Stage 1: Schema Generation (Weaver)

- Uses the official `otel/weaver:v0.21.2` image
- Reads the telemetry schema from `/telemetry-schema` directory
- Generates service-centric Markdown documentation files
- Generates fully resolved schema as JSON

### Stage 2: Static Site Build (MkDocs)

- Uses Python 3.14 slim-bookworm image
- Installs MkDocs and Material theme
- Builds static HTML site from generated Markdown
- Optimizes assets for production delivery

### Stage 3: Production Server (nginx + OpenTelemetry)

- Uses `nginxinc/nginx-unprivileged:<version>-otel`
- Serves pre-built static site
- **Full OpenTelemetry instrumentation** with optimized configuration

## OpenTelemetry Instrumentation

The service includes production-ready OpenTelemetry tracing with:

### Batch Configuration

- **Interval**: 5s export frequency
- **Batch size**: 256 spans per batch (optimized for static content)
- **Batch count**: 2 pending batches per worker (reduced memory footprint)

### Low-Cardinality Span Names

Implements route parameterization to avoid high cardinality:

- `/attributes/*.html` -> `GET /attributes/{business_domain}`
- `/services/*.html` -> `GET /services/{service_name}`
- `/index.html` -> `GET /index`
- `/` -> `GET /`

### Tracing Exclusions

Static assets and health checks are excluded from tracing for **80-90%
span volume reduction**:

- Static files (CSS, JS, images, fonts)
- Search indexes
- Health check endpoint (`/status`)

This follows
[OpenTelemetry HTTP semantic conventions](https://opentelemetry.io/docs/specs/semconv/http/http-spans/)
for optimal observability.

## Usage

### Running the telemetry-docs service

The application can be run with the rest of the demo using the documented
[docker compose or make commands](https://opentelemetry.io/docs/demo/#running-the-demo).

### Accessing the Documentation

Once the service is running, access the documentation at:
<http://localhost:8080/telemetry>

### Building the telemetry-docs service

```bash
docker compose build telemetry-docs
```

## Configuration

### Environment Variables

The service requires the following environment variables:

- `TELEMETRY_DOCS_PORT` - Port for the nginx server (default: 8000)
- `OTEL_COLLECTOR_HOST` - OpenTelemetry Collector hostname
- `OTEL_COLLECTOR_PORT_GRPC` - OTel Collector gRPC port (default: 4317)
- `OTEL_SERVICE_NAME` - Service name for telemetry (default: `telemetry-docs`)

### nginx Configuration

The service uses a templated nginx configuration (`nginx.conf.template`) with
environment variable substitution. Key features:

- **Static file serving** from `/static` directory
- **OpenTelemetry module** for distributed tracing
- **Cache headers** for static assets (1 year expiry)
- **Health check endpoint** at `/status` (excluded from tracing)
- **gzip compression** for efficient content delivery

## References

- [OpenTelemetry Weaver](https://github.com/open-telemetry/weaver)
- [nginx OpenTelemetry Module](https://github.com/nginxinc/nginx-otel)
- [OpenTelemetry HTTP Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/http/http-spans/)
- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
