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

See [docs/local-setup.md](docs/local-setup.md) for detailed instructions.

## Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                      YOUR LAPTOP                             │
│                                                              │
│  incidentfox/scripts/build-all.sh                           │
│              ↓                                               │
│         Terraform deploys:                                   │
└──────────────────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                      AWS CLOUD                               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  VPC (10.0.0.0/16)                                     │ │
│  │                                                          │ │
│  │  ┌─────────────┐         ┌─────────────┐              │ │
│  │  │   Public    │         │   Private   │              │ │
│  │  │  Subnets    │         │  Subnets    │              │ │
│  │  │  (2 AZs)    │         │  (2 AZs)    │              │ │
│  │  │             │         │             │              │ │
│  │  │ ┌─────┐     │         │  ┌────────┐ │              │ │
│  │  │ │ NLB │←────┼─────────┼─→│  EKS   │ │              │ │
│  │  │ └─────┘     │         │  │ Nodes  │ │              │ │
│  │  │             │         │  │  (8x)  │ │              │ │
│  │  └─────────────┘         │  └────────┘ │              │ │
│  │                           │             │              │ │
│  │                           │  25 services│              │ │
│  │                           └─────────────┘              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  AWS Secrets Manager                                   │ │
│  │  • incidentfox-demo/postgres                           │ │
│  │  • incidentfox-demo/grafana                            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Services Overview

**15+ Microservices:**
- `frontend`, `cart`, `checkout`, `payment` - E-commerce
- `product-catalog`, `recommendation` - Product management
- `shipping`, `ad`, `email`, `quote`, `currency` - Supporting services
- `accounting`, `fraud-detection` - Backend processing

**Observability Stack:**
- `prometheus` - Metrics storage
- `jaeger` - Distributed tracing
- `opensearch` - Log storage
- `grafana` - Visualization
- `otel-collector` - Telemetry aggregation

**Infrastructure:**
- `kafka` - Message queue
- `postgresql` - Database
- `valkey` - Cache
- `flagd` - Feature flags

### Key Infrastructure Components

**Terraform Modules:**
- `modules/vpc/` - VPC with public/private subnets, NAT gateways
- `modules/eks/` - EKS cluster, node groups, OIDC for IRSA
- `modules/secrets/` - AWS Secrets Manager with random passwords
- `modules/irsa/` - IAM roles for Kubernetes ServiceAccounts

**Network Design:**
- **Public subnets** - LoadBalancers (exposed to internet via IGW)
- **Private subnets** - EKS nodes (outbound only via NAT)
- **Multi-AZ** - High availability (2 availability zones)

**Compute:**
- **2 node groups** - System (2x t3.small) vs Application (6x t3.small)
- **Why separate?** - Isolate stable monitoring from variable workloads

**Security:**
- **IRSA** - Pods get temporary AWS credentials (no long-lived keys)
- **AWS Secrets Manager** - Centralized, encrypted secret storage
- **Private subnets** - Nodes not directly accessible from internet

### Key Components

**Master Scripts:**
- `scripts/build-all.sh` - One-command deploy/destroy/status
- `scripts/trigger-incident.sh` - Trigger any of 12 failure scenarios  
- `scripts/export-secrets-to-1password.sh` - Backup secrets

**Terraform Modules:**
- `modules/vpc/` - VPC with public/private subnets, NAT gateways
- `modules/eks/` - EKS cluster, node groups, OIDC
- `modules/secrets/` - AWS Secrets Manager with random passwords
- `modules/irsa/` - IAM roles for Kubernetes pods

**Helm Values:**
- `helm/values-aws-simple.yaml` - Resource limits for t3.small nodes

### Design Decisions

**Network: Public/Private Subnet Split**
- Public subnets: LoadBalancers (Internet Gateway for inbound)
- Private subnets: EKS nodes (NAT Gateway for outbound only)
- Multi-AZ: High availability across 2 zones

**Compute: Two Node Groups**
- System nodes (2x t3.small): Stable monitoring/DNS workloads
- Application nodes (6x t3.small): Demo services, can scale independently

**Instance Size: t3.small**
- Constraint: AWS Free Tier restriction
- Solution: More smaller nodes (better distribution)
- Total: 8 nodes = 16 vCPU, 16GB RAM

**Secrets: External Secrets Operator**
- AWS Secrets Manager is source of truth
- Automatic sync to Kubernetes (no manual copying)
- Rotation-ready architecture

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

See [docs/agent-integration.md](docs/agent-integration.md) for connection details.

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

See [docs/incident-scenarios.md](docs/incident-scenarios.md) for complete catalog.

## Documentation

### For Agent Developers (Start Here!)

**[AGENT-DEV-GUIDE.md](AGENT-DEV-GUIDE.md)** - Quick start for developers using the playground to build AI agents. No infrastructure knowledge needed.

### Complete Documentation

| Document | Purpose |
|----------|---------|
| **README.md** | This file - complete overview, architecture, components |
| **[AGENT-DEV-GUIDE.md](AGENT-DEV-GUIDE.md)** | **For agent developers** - endpoints, incidents, testing |
| **[docs/aws-deployment.md](docs/aws-deployment.md)** | Deploy to AWS EKS and operate |
| **[docs/coralogix.md](docs/coralogix.md)** | Hook lab telemetry up to Coralogix |
| **[docs/local-setup.md](docs/local-setup.md)** | Run locally with Docker or kind |
| **[docs/secrets.md](docs/secrets.md)** | Secrets management and security |
| **[docs/agent-integration.md](docs/agent-integration.md)** | Connect your AI agent (technical details) |
| **[docs/incident-scenarios.md](docs/incident-scenarios.md)** | Trigger and test incidents |

See [docs/README.md](docs/README.md) for detailed navigation guide.

## Repository Structure

```
incidentfox/
├── README.md                        # Overview and navigation
├── docs/                            # All documentation
│   ├── architecture.md             # System design and how it works
│   ├── aws-deployment.md           # AWS EKS deployment
│   ├── coralogix.md                # Coralogix integration
│   ├── local-setup.md              # Docker/k8s local setup
│   ├── secrets.md                  # Secrets management
│   ├── agent-integration.md        # Connect AI agent
│   └── incident-scenarios.md       # Incident catalog
├── scripts/
│   ├── build-all.sh                # Master deployment script
│   ├── trigger-incident.sh         # Incident trigger
│   ├── export-secrets-to-1password.sh
│   ├── scenarios/                  # 12 incident scenarios
│   └── load/                       # Load generation
├── agent-config/
│   ├── endpoints.yaml              # Observability endpoints
│   └── example-config.yaml         # Agent config template
├── terraform/                      # AWS infrastructure (Terraform)
│   ├── main.tf
│   ├── variables.tf
│   ├── terraform.tfvars.example
│   └── modules/                    # VPC, EKS, Secrets, IRSA
└── helm/                           # Kubernetes deployment (Helm)
    └── values-aws-simple.yaml
```

## Cost Estimate (AWS)

**Monthly cost (24/7 operation):**
- EKS Control Plane: $73
- 8x t3.small nodes: ~$120
- 2x NAT Gateways: ~$64
- 3x Network Load Balancers: ~$48
- EBS Storage (~100GB): ~$10
- Secrets Manager (2 secrets): ~$1
- **Total: ~$316/month** (~$10.50/day)

See [docs/aws-deployment.md](docs/aws-deployment.md) for cost optimization strategies.

## Upstream Compatibility

All customizations are in the `incidentfox/` directory:
- `main` branch: tracks upstream OpenTelemetry Demo
- `incidentfox` branch: our additions (this)
- Minimal changes to upstream code

Sync with upstream:
```bash
git checkout main && git pull upstream main && git push origin main
git checkout incidentfox && git rebase main
```

## AWS Deployment

```bash
cd incidentfox
./scripts/build-all.sh deploy
```

Deploys complete lab to AWS EKS with VPC, secrets management, and all 25 services. See [docs/aws-deployment.md](docs/aws-deployment.md) for details.

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

