# OpenTelemetry Demo Helm Chart

This Helm chart deploys the OpenTelemetry Demo application with Grafana for visualization, OpenTelemetry Collector for telemetry collection, and various microservices that make up the demo application.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.8.0+
- Azure Data Explorer (ADX) cluster for telemetry storage (optional, can be configured via values)

## Installation

### Add the repository (if published)

```bash
helm repo add opentelemetry-demo https://example.com/charts
helm repo update
```

### Install the chart

```bash
# Install with default values
helm install my-otel-demo ./opentelemetry-demo-chart

# Install in a specific namespace
helm install my-otel-demo ./opentelemetry-demo-chart --namespace otel-demo --create-namespace

# Install with custom values
helm install my-otel-demo ./opentelemetry-demo-chart -f custom-values.yaml
```

## Uninstallation

```bash
helm uninstall my-otel-demo
```

## Configuration

The following table lists the configurable parameters of the OpenTelemetry Demo chart and their default values.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespace` | Namespace to deploy the demo into | `otel-demo` |
| `azure_tenant_id` | Azure tenant ID for workload identity | `""` |
| `grafana.enabled` | Enable Grafana deployment | `true` |
| `grafana.adminUser` | Grafana admin username | `admin` |
| `grafana.adminPassword` | Grafana admin password | `admin` |
| `grafana.plugins` | Grafana plugins to install | `grafana-azure-data-explorer-datasource` |
| `grafana.clientid` | Azure client ID for Grafana workload identity | `""` |
| `otelCollector.enabled` | Enable OTel Collector deployment | `true` |
| `otelCollector.version` | OTel Collector version | `0.135.0` |
| `otelCollector.clientid` | Azure client ID for OTel Collector workload identity | `""` |
| `serviceAccount.create` | Create service account | `true` |
| `serviceAccount.name` | Service account name | `opentelemetry-demo` |
| `featureFlags.*` | Feature flag configurations | `off` |

### Example: Custom values

Create a `custom-values.yaml` file:

```yaml
namespace: my-otel-demo
azure_tenant_id: "your-tenant-id"

grafana:
  adminPassword: mySecurePassword
  clientid: "your-grafana-client-id"

otelCollector:
  clientid: "your-otel-collector-client-id"

featureFlags:
  imageSlowLoad: "5sec"
  loadGeneratorFloodHomepage: 100
```

Then install with:

```bash
helm install my-otel-demo ./opentelemetry-demo-chart -f custom-values.yaml
```

## Accessing the Application

After installation, you can access the various components:

- **Frontend**: Port-forward to access the web UI
  ```bash dashboards
  ```bash
  kubectl port-forward -n otel-demo svc/grafana 3000:3000
  ```
  Then open http://localhost:3000/grafana
  Default credentials: admin/admin (configurable via values)

## Components

This chart deploys the following components:

### Observability Stack
- **Grafana**: Visualization and dashboards with Azure Data Explorer datasource support
- **OpenTelemetry Collector**: Collects traces, metrics, and logs from all services
  - Configured to export to Azure Data Explorer (ADX)
  - Includes Kubernetes attribute enrichment
  - Resource detection and batching

### Demo Microservices
- **accounting**: Accounting service (C#)
- **ad**: Ad service (Java)
- **cart**: Shopping cart service (C#)
- **checkout**: Checkout service (Go)
- **currency**: Currency conversion service (C++)
- **email**: Email service (Ruby)
- **fraud-detection**: Fraud detection service (Kotlin)
- **frontend**: Web frontend (Next.js)
- **frontend-proxy**: Envoy proxy for frontend
- **image-provider**: Static image provider (Nginx)
- **kafka**: Kafka message broker
- **load-generator**: Load generator
- **payment**: Payment service (JavaScript)
- **postgresql**: PostgreSQL database
- **product-catalog**: Product catalog service (Go)
- **quote**: Quote service (PHP)
- **recommendation**: Recommendation service (Python)
- **shipping**: Shipping service (Rust)
- **valkey-cart**: Redis-compatible cache (Valkey)
- **flagd**: Feature flag service

## Azure Integration

This chart is designed to work with Azure services using workload identity:

### Azure Data Explorer (ADX)
The OpenTelemetry Collector is configured to export telemetry data to Azure Data Explorer. Configure the following environment variables or use workload identity:

- `ADX_CLUSTER_URI`: Your ADX cluster URI
- `ADX_DATABASE`: Database name in ADX
- `AZURE_CLIENT_ID`: Client ID for authentication (or use `otelCollector.clientid`)
- `AZURE_CLIENT_SECRET`: Client secret for authentication
- `AZURE_TENANT_ID`: Azure tenant ID (or use `azure_tenant_id`)

### Workload Identity
The chart creates service accounts with Azure workload identity annotations for:
- **Grafana** (`grafana-sa`): To access ADX for querying data
- **OTel Collector** (`otel-collector-sa`): To send data to ADX

Configure the client IDs in your values file:
```yaml
azure_tenant_id: "your-tenant-id"
grafana:
  clientid: "your-grafana-managed-identity-client-id"
otelCollector:
  clientid: "your-otel-collector-managed-identity-client-id"
```
  Default credentials: admin/admin (configurable via values)
- **Jaeger UI**: Port-forward to access Jaeger
  ```bash
  kubectl port-forward -n otel-demo svc/jaeger 16686:16686
  ```
  Then open http://localhost:16686

## Feature Flags

The demo includes several feature flags to simulate various failure scenarios:

- `productCatalogFailure`: Fail product catalog service on a specific product
- `recommendationCacheFailure`: Fail recommendation service cache
- `adManualGc`: Triggers full manual garbage collections in the ad service
- `adHighCpu`: Triggers high cpu load in the ad service
- `adFailure`: Fail ad service
- `kafkaQueueProblems`: Overloads Kafka queue
- `cartFailure`: Fail cart service
- `paymentFailure`: Fail payment service charge requests
- `paymentUnreachable`: Payment service is unavailable
- `loadGeneratorFloodHomepage`: Flood the frontend with requests
- `imageSlowLoad`: Slow loading images in the frontend

## Troubleshooting

### Check pod status

```bash
kubectl get pods -n otel-demo
```

### View logs

```bash
kubectl logs -n otel-demo <pod-name>
```

### Describe resources

```bash
kubectl describe pod -n otel-demo <pod-name>
```

## Contributing

Contributions are welcome! Please see the main OpenTelemetry Demo repository for contribution guidelines.

## License

Apache License 2.0
