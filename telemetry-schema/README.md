# OpenTelemetry Demo Telemetry Schema

This directory contains the semantic conventions and telemetry schema for the OpenTelemetry Demo application, defining all custom attributes and metrics used across the demo services.

## Structure

The schema is organized into three directories:

- **`attributes/`** - Attribute definitions organized by business domain (product, user, order, shipping, misc)
- **`services/`** - Service-specific attribute references (one file per service)
- **`metrics/`** - Metric definitions (one file per service that produces metrics)

## Documentation

To view the generated documentation:

```bash
docker compose up telemetry-docs
```

Access at: http://localhost:8001

## Purpose

This schema provides a single source of truth for all custom telemetry in the demo application, ensuring naming consistency and enabling validation of instrumentation code.
