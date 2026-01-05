# OpenTelemetry Demo Helm Chart - Quick Start

## Chart Structure

```
opentelemetry-demo-chart/
├── Chart.yaml                 # Chart metadata
├── values.yaml               # Default configuration values
├── README.md                 # Comprehensive documentation
├── .helmignore              # Files to ignore when packaging
└── templates/
    ├── NOTES.txt            # Post-installation notes
    ├── _helpers.tpl         # Template helpers
    └── opentelemetry-demo.yaml  # Main Kubernetes manifests
```

## Prerequisites

Before using this Helm chart, ensure you have:

1. **Helm 3.x** installed:
   ```bash
   # macOS
   brew install helm
   
   # Linux
   curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
   ```

2. **kubectl** configured to access your Kubernetes cluster

3. **Kubernetes cluster** (1.24+) with:
   - At least 8GB RAM available
   - Storage class for persistent volumes (for OpenSearch and Prometheus)

## Installation Steps

### 1. Validate the chart

```bash
cd /Users/michaelliav/projects/adx-opentelemetry-demo/kubernetes
helm lint opentelemetry-demo-chart
```

### 2. Install the chart (dry-run first)

```bash
# Dry-run to see what will be deployed
helm install my-otel-demo opentelemetry-demo-chart --dry-run --debug

# Install for real
helm install my-otel-demo opentelemetry-demo-chart
```

### 3. Install with custom namespace

```bash
helm install my-otel-demo opentelemetry-demo-chart \
  --create-namespace \
  --namespace otel-demo
```

### 4. Install with custom values

```bash
# Create custom-values.yaml
cat > custom-values.yaml <<EOF
namespace: my-demo
grafana:
  adminPassword: secure-password
featureFlags:
  imageSlowLoad: "5sec"
EOF

# Install with custom values
helm install my-otel-demo opentelemetry-demo-chart -f custom-values.yaml
```

## Verify Installation

```bash
# Check Helm release status
helm status my-otel-demo

# List all pods
kubectl get pods -n otel-demo

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n otel-demo --timeout=300s
```

## Accessing Services

After installation, follow the instructions in the NOTES output, or run:

```bash
helm status my-otel-demo
```

Quick access commands:

```bash
# Frontend
kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080

# Grafana
kubectl port-forward -n otel-demo svc/grafana 3000:3000

# Jaeger
kubectl port-forward -n otel-demo svc/jaeger 16686:16686
```

## Upgrading

```bash
# Upgrade with new values
helm upgrade my-otel-demo opentelemetry-demo-chart -f custom-values.yaml

# View upgrade history
helm history my-otel-demo
```

## Uninstalling

```bash
# Uninstall the release
helm uninstall my-otel-demo

# If you created a namespace, delete it
kubectl delete namespace otel-demo
```

## Customization Examples

### Example 1: Change namespace and disable components

```yaml
# my-values.yaml
namespace: prod-otel

grafana:
  enabled: false

opensearch:
  enabled: false
```

### Example 2: Enable failure scenarios

```yaml
# chaos-values.yaml
featureFlags:
  adHighCpu: "on"
  paymentFailure: "50%"
  imageSlowLoad: "10sec"
  loadGeneratorFloodHomepage: 100
```

Install with:
```bash
helm install chaos-demo opentelemetry-demo-chart -f chaos-values.yaml
```

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl get pods -n otel-demo

# Describe problematic pod
kubectl describe pod <pod-name> -n otel-demo

# View logs
kubectl logs <pod-name> -n otel-demo
```

### Helm chart validation errors

```bash
# Template the chart to see generated YAML
helm template my-otel-demo opentelemetry-demo-chart > output.yaml

# Check for errors
helm lint opentelemetry-demo-chart
```

### Resource constraints

If pods are pending due to insufficient resources, you can add resource limits/requests in values.yaml (requires extending the chart).

## Package and Share

To package the chart for distribution:

```bash
# Package the chart
helm package opentelemetry-demo-chart

# This creates: opentelemetry-demo-2.1.3.tgz

# Install from package
helm install my-otel-demo opentelemetry-demo-2.1.3.tgz
```

## Next Steps

- Read the full [README.md](README.md) for detailed configuration options
- Explore [OpenTelemetry Demo documentation](https://opentelemetry.io/docs/demo/)
- Customize the chart for your environment
- Add to your Helm repository for easy sharing

## Contributing

To improve this Helm chart:
1. Modify templates or values as needed
2. Run `helm lint` to validate
3. Test in a development cluster
4. Submit improvements back to the project
