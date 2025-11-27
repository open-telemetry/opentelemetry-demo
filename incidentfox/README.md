# IncidentFox Lab Environment

This directory contains IncidentFox-specific configurations, scripts, and documentation for using the OpenTelemetry Demo as an AI SRE training and testing playground.

## Overview

**IncidentFox** is an AI SRE / AI on-call agent that integrates with metrics, logs, traces, and Kubernetes to automatically detect, diagnose, and respond to incidents.

This fork of the OpenTelemetry Demo serves as:
- A realistic microservices environment for testing our AI agent
- An "internal production" lab with real observability data
- A reproducible incident playground for agent training and validation

## Quick Start

### Local Development (Docker Compose)

```bash
# From repo root
docker compose up -d

# Access the demo
open http://localhost:8080

# Access observability UIs
open http://localhost:8080/grafana      # Grafana dashboards
open http://localhost:8080/jaeger/ui    # Jaeger traces
open http://localhost:8080/loadgen      # Load generator UI
```

### Kubernetes (Local)

```bash
# Using kind or k3d
kind create cluster --name incidentfox-lab

# Apply the manifests
kubectl apply -f kubernetes/opentelemetry-demo.yaml

# Port forward to access
kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080
```

For detailed setup instructions, see [`docs/local-setup.md`](docs/local-setup.md).

## Architecture

The demo consists of 15+ microservices implementing an e-commerce application ("Astronomy Shop"):

**Core Services:**
- `frontend` - Next.js web application
- `checkout` - Order processing (Go)
- `cart` - Shopping cart (C#)
- `product-catalog` - Product database (Go)
- `recommendation` - ML recommendations (Python)
- `payment` - Payment processing (Node.js)
- `shipping` - Shipping calculation (Rust)
- `ad` - Advertisement service (Java)
- `email` - Email notifications (Ruby)
- `accounting` - Order accounting (C#)
- `fraud-detection` - Fraud analysis (Kotlin)
- `currency` - Currency conversion (C++)
- `quote` - Shipping quotes (PHP)

**Observability Stack:**
- `otel-collector` - OpenTelemetry Collector (metrics, logs, traces)
- `prometheus` - Metrics storage and querying
- `jaeger` - Distributed tracing backend
- `opensearch` - Log storage and search
- `grafana` - Visualization dashboards

**Infrastructure:**
- `kafka` - Message queue for async processing
- `postgresql` - Database for accounting/reviews
- `valkey` - Redis-compatible cache for cart
- `flagd` - Feature flag service for triggering failures

## Observability Endpoints

All endpoints documented in [`agent-config/endpoints.yaml`](agent-config/endpoints.yaml):

| Component | Endpoint | Purpose |
|-----------|----------|---------|
| Prometheus | `http://localhost:9090` | Metrics query API |
| Jaeger UI | `http://localhost:16686` | Trace visualization |
| Jaeger Query | `http://localhost:16685` | Trace query API |
| Grafana | `http://localhost:3000/grafana` | Dashboards |
| OpenSearch | `http://localhost:9200` | Log search API |
| OTel Collector (OTLP/gRPC) | `http://localhost:4317` | Telemetry ingest |
| OTel Collector (OTLP/HTTP) | `http://localhost:4318` | Telemetry ingest |

See [`docs/agent-integration.md`](docs/agent-integration.md) for details on connecting the IncidentFox agent.

## Incident Scenarios

The demo includes built-in failure scenarios controlled via feature flags. Use our wrapper scripts for easy triggering:

```bash
# Trigger a specific incident
./incidentfox/scripts/trigger-incident.sh high-cpu

# Available scenarios
./incidentfox/scripts/trigger-incident.sh --list
```

**Available Scenarios:**
- `high-cpu` - Ad service CPU spike
- `memory-leak` - Email service memory leak
- `service-failure` - Payment service failures
- `latency-spike` - Image loading delays
- `kafka-lag` - Message queue backlog
- `cache-failure` - Recommendation cache errors
- `catalog-failure` - Product catalog errors

See [`docs/incident-scenarios.md`](docs/incident-scenarios.md) for detailed descriptions and expected behaviors.

## Repository Structure

```
incidentfox/
├── README.md                    # This file
├── docs/
│   ├── local-setup.md          # Detailed local setup
│   ├── aws-deployment.md       # AWS deployment guide
│   ├── agent-integration.md    # Agent connection guide
│   └── incident-scenarios.md   # Scenario catalog
├── scripts/
│   ├── trigger-incident.sh     # Master incident script
│   ├── scenarios/              # Individual scenario scripts
│   └── load/                   # Load generation scripts
├── agent-config/
│   ├── example-config.yaml     # Example agent config
│   └── endpoints.yaml          # All observability endpoints
├── terraform/                  # AWS infrastructure code
└── helm/                       # Kubernetes Helm charts
```

## Upstream Compatibility

This fork maintains compatibility with the upstream OpenTelemetry Demo:

- `main` branch tracks upstream changes
- `incidentfox` branch contains our customizations
- All IncidentFox additions are in the `incidentfox/` directory
- Minimal changes to upstream files (clearly marked with `# IncidentFox:` comments)

To sync with upstream:
```bash
git checkout main
git pull upstream main
git push origin main

git checkout incidentfox
git rebase main
```

## AWS Deployment

The demo can be deployed to AWS EKS for production-grade testing. See [`docs/aws-deployment.md`](docs/aws-deployment.md) and the [`terraform/`](terraform/) directory.

## Development Workflow

1. **Start the demo**: `docker compose up -d`
2. **Trigger an incident**: `./incidentfox/scripts/trigger-incident.sh service-failure`
3. **Point your agent at the observability endpoints**: See `agent-config/endpoints.yaml`
4. **Watch the agent respond**: Monitor agent logs and actions
5. **Validate the response**: Check if the agent correctly diagnosed and resolved the issue

## Contributing

For IncidentFox-specific changes:
1. Work on the `incidentfox` branch
2. Keep changes isolated to the `incidentfox/` directory when possible
3. Mark any upstream file changes with `# IncidentFox:` comments
4. Document new scenarios in `docs/incident-scenarios.md`

## Resources

- [OpenTelemetry Demo Docs](https://opentelemetry.io/docs/demo/)
- [Upstream Repository](https://github.com/open-telemetry/opentelemetry-demo)
- [Locust Load Generator Docs](https://docs.locust.io/)
- [Feature Flags](../src/flagd/demo.flagd.json)

## Support

For IncidentFox-specific issues, reach out to the IncidentFox team.
For upstream demo issues, see the [OpenTelemetry Demo repository](https://github.com/open-telemetry/opentelemetry-demo).

