# IncidentFox: Kubernetes Helm Charts

This directory will contain Helm charts for deploying the OpenTelemetry Demo to Kubernetes (local or AWS EKS).

## Status

✅ **Implemented** - Helm values files for AWS deployment are ready.

The upstream OpenTelemetry Demo has official Helm charts, but we may need to:
1. Fork and customize them for our needs
2. Add AWS-specific configurations
3. Add IncidentFox-specific monitoring and integrations

## Planned Approach

### Option 1: Use Upstream Charts with Overrides

```bash
# Add upstream repo
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# Install with custom values
helm install otel-demo open-telemetry/opentelemetry-demo \
  -n otel-demo --create-namespace \
  -f values-incidentfox.yaml \
  -f values-aws.yaml
```

### Option 2: Fork and Customize

Copy charts from `/Users/apple/Desktop/opentelemetry-helm-charts/opentelemetry-demo` and:
- Add AWS-specific configurations (ALB ingress, IRSA, etc.)
- Customize resource limits for our use case
- Add IncidentFox agent integration
- Pre-configure dashboards and alerts

## Planned Structure

```
helm/
├── README.md                     # This file
├── opentelemetry-demo/          # Main chart
│   ├── Chart.yaml               # Chart metadata
│   ├── values.yaml              # Default values
│   ├── values-aws.yaml          # AWS EKS overrides
│   ├── values-local.yaml        # Local (kind/k3d) overrides
│   ├── values-incidentfox.yaml  # IncidentFox customizations
│   ├── templates/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   ├── configmap.yaml
│   │   └── ...
│   └── charts/                  # Subcharts
│       ├── jaeger/
│       ├── prometheus/
│       ├── grafana/
│       └── opensearch/
└── incidentfox-agent/           # Agent chart (optional)
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
```

## Customizations Needed

### AWS EKS Specific

```yaml
# values-aws.yaml
ingress:
  enabled: true
  className: alb
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...

# Use EBS for persistence
persistence:
  storageClassName: gp3

# IRSA for AWS services
serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::...

# Resource limits appropriate for AWS instance types
resources:
  limits:
    memory: 500Mi
  requests:
    memory: 256Mi
```

### IncidentFox Specific

```yaml
# values-incidentfox.yaml
# Pre-configure feature flags for incidents
flagd:
  config:
    # All flags default to "off" for safe baseline

# Add agent integration annotations
podAnnotations:
  incidentfox.io/monitored: "true"
  incidentfox.io/environment: "lab"

# Export metrics in agent-friendly format
metrics:
  serviceMonitor:
    enabled: true
    additionalLabels:
      incidentfox: "true"
```

## Usage (Planned)

### Local Development (kind/k3d)

```bash
# Create cluster
kind create cluster --name incidentfox-lab

# Install chart
cd incidentfox/helm
helm install otel-demo ./opentelemetry-demo \
  -n otel-demo --create-namespace \
  -f opentelemetry-demo/values-local.yaml

# Port forward
kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080
```

### AWS EKS

```bash
# Assuming EKS cluster is ready
aws eks update-kubeconfig --name incidentfox-demo --region us-west-2

# Install with AWS values
cd incidentfox/helm
helm install otel-demo ./opentelemetry-demo \
  -n otel-demo --create-namespace \
  -f opentelemetry-demo/values-aws.yaml \
  -f opentelemetry-demo/values-incidentfox.yaml

# Check status
kubectl get pods -n otel-demo
kubectl get ingress -n otel-demo
```

### Upgrade

```bash
# Update values
vim opentelemetry-demo/values-incidentfox.yaml

# Upgrade release
helm upgrade otel-demo ./opentelemetry-demo \
  -n otel-demo \
  -f opentelemetry-demo/values-aws.yaml \
  -f opentelemetry-demo/values-incidentfox.yaml
```

### Uninstall

```bash
helm uninstall otel-demo -n otel-demo
kubectl delete namespace otel-demo
```

## Development Tasks

### Priority 1: Basic Deployment
- [ ] Copy/reference upstream charts
- [ ] Create values-local.yaml for kind/k3d
- [ ] Test local deployment
- [ ] Document installation steps

### Priority 2: AWS Support
- [ ] Create values-aws.yaml with ALB ingress
- [ ] Configure EBS storage classes
- [ ] Set up IRSA for AWS services
- [ ] Add SSL/TLS support
- [ ] Test on EKS

### Priority 3: IncidentFox Integration
- [ ] Create values-incidentfox.yaml
- [ ] Pre-configure dashboards
- [ ] Add agent-specific annotations
- [ ] Set up ServiceMonitors
- [ ] Document agent integration

### Priority 4: Production Readiness
- [ ] Add PodDisruptionBudgets
- [ ] Configure HorizontalPodAutoscalers
- [ ] Set up NetworkPolicies
- [ ] Add resource quotas
- [ ] Implement backup/restore
- [ ] Add monitoring and alerting

## Upstream Chart Location

The official charts are likely at:
```
/Users/apple/Desktop/opentelemetry-helm-charts/opentelemetry-demo
```

We can either:
1. Reference them directly
2. Copy and customize
3. Use as a dependency in our Chart.yaml

## Resources

- [Helm Documentation](https://helm.sh/docs/)
- [OpenTelemetry Demo Helm Charts](https://github.com/open-telemetry/opentelemetry-helm-charts)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)

## Contributing

When implementing Helm charts:
1. Follow Helm best practices
2. Use meaningful value names
3. Add helpful comments in values.yaml
4. Test on both local and cloud environments
5. Document all customizations
6. Version charts properly (semver)
7. Add NOTES.txt with post-install instructions

## Support

For questions about Kubernetes deployment, contact the SRE team.

