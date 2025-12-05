# Telemetry Documentation Service

This service generates and hosts comprehensive documentation for the OpenTelemetry Demo's telemetry schema using [OpenTelemetry Weaver](https://github.com/open-telemetry/weaver) and [MkDocs](https://www.mkdocs.org/).

## Overview

The telemetry-docs service provides a web-based documentation interface that documents all custom attributes and metrics used across the OpenTelemetry Demo application. The documentation is automatically generated from the YAML schema definitions in the `telemetry-schema/` directory.

## Architecture

The service uses a two-stage Docker build:

### Stage 1: Weaver Builder
- Uses the official `otel/weaver:latest` image
- Reads the telemetry schema from `/telemetry-schema` directory
- Generates Markdown documentation files

### Stage 2: MkDocs Server
- Uses Python 3.11 slim image
- Installs MkDocs and Material theme
- Copies the generated documentation from Stage 1
- Serves the documentation on port 8000 as a live server

## Usage

### Starting the Service

```bash
# Start just the telemetry-docs service
docker compose up telemetry-docs

# Or start all services including telemetry-docs
docker compose up
```

### Accessing the Documentation

Once the service is running, access the documentation at:

```
http://localhost:8001
```

### Building the Service

```bash
# Build the telemetry-docs image
docker compose build telemetry-docs
```

## References

- [OpenTelemetry Weaver](https://github.com/open-telemetry/weaver)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
