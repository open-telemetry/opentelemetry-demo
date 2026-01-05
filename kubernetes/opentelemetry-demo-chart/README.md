# OpenTelemetry Demo Helm Chart

This Helm chart deploys the OpenTelemetry Demo application with all its components including Jaeger, Prometheus, Grafana, OpenSearch, and various microservices.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.8.0+
- Persistent Volume provisioner support in the underlying infrastructure (for OpenSearch and Prometheus)

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
| `createNamespace` | Create namespace if it doesn't exist | `true` |
| `grafana.enabled` | Enable Grafana deployment | `true` |
| `grafana.adminUser` | Grafana admin username | `admin` |
| `grafana.adminPassword` | Grafana admin password | `admin` |
| `grafana.plugins` | Grafana plugins to install | `grafana-opensearch-datasource` |
| `opensearch.enabled` | Enable OpenSearch deployment | `true` |
| `opensearch.clusterName` | OpenSearch cluster name | `opensearch-cluster` |
| `opensearch.maxUnavailable` | Max unavailable pods for PDB | `1` |
| `jaeger.enabled` | Enable Jaeger deployment | `true` |
| `otelCollector.enabled` | Enable OTel Collector deployment | `true` |
| `prometheus.enabled` | Enable Prometheus deployment | `true` |
| `featureFlags.*` | Feature flag configurations | `off` |

### Example: Custom values

Create a `custom-values.yaml` file:

```yaml
namespace: my-otel-demo

grafana:
  adminPassword: mySecurePassword

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
  ```bash
  kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080
  ```
  Then open http://localhost:8080

- **Grafana**: Port-forward to access Grafana
  ```bash
  kubectl port-forward -n otel-demo svc/grafana 3000:3000
  ```
  Then open http://localhost:3000/grafana

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
