# Local Setup Guide

This guide walks through setting up the OpenTelemetry Demo locally for IncidentFox agent development and testing.

## Prerequisites

### For Docker Compose

- **Docker Desktop** (4.24+) or Docker Engine (24.0+)
- **Docker Compose** v2.0+
- **8 GB RAM** minimum (16 GB recommended)
- **10 GB disk space**

### For Kubernetes

- **kubectl** (1.27+)
- **Helm** (3.12+)
- **kind** or **k3d** for local cluster
- **16 GB RAM** recommended

## Option 1: Docker Compose (Recommended for Local Dev)

### Step 1: Clone and Setup

```bash
git clone <your-fork-url> aws-playground
cd aws-playground
git checkout incidentfox
```

### Step 2: Start the Demo

```bash
# Start all services
docker compose up -d

# Check service health
docker compose ps

# View logs
docker compose logs -f
```

### Step 3: Access the Services

The frontend proxy (Envoy) exposes all services on `localhost:8080`:

| Service | URL | Description |
|---------|-----|-------------|
| Web Store | http://localhost:8080 | Main application |
| Grafana | http://localhost:8080/grafana | Dashboards (admin/admin) |
| Jaeger UI | http://localhost:8080/jaeger/ui | Distributed tracing |
| Load Generator | http://localhost:8080/loadgen | Locust UI |
| Feature Flags | http://localhost:8080/feature | flagd UI |
| Prometheus | http://localhost:9090 | Direct access (not proxied) |

### Step 4: Generate Load

The load generator starts automatically. To customize:

```bash
# Access Locust UI
open http://localhost:8080/loadgen

# Or use our scripts
./incidentfox/scripts/load/normal-load.sh
./incidentfox/scripts/load/spike-load.sh
```

### Step 5: Trigger an Incident

```bash
# List available scenarios
./incidentfox/scripts/trigger-incident.sh --list

# Trigger a specific scenario
./incidentfox/scripts/trigger-incident.sh high-cpu

# Monitor the incident
docker compose logs -f ad
```

### Step 6: Stop the Demo

```bash
# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

## Option 2: Kubernetes with kind

### Step 1: Create Local Cluster

```bash
# Create a kind cluster
cat <<EOF | kind create cluster --name incidentfox-lab --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 8080
    hostPort: 8080
    protocol: TCP
EOF
```

### Step 2: Deploy the Demo

```bash
# Apply the Kubernetes manifests
kubectl apply -f kubernetes/opentelemetry-demo.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod --all -n otel-demo --timeout=300s

# Check pod status
kubectl get pods -n otel-demo
```

### Step 3: Access Services

```bash
# Port forward to frontend proxy
kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080 &

# Port forward to Prometheus
kubectl port-forward -n otel-demo svc/prometheus 9090:9090 &

# Access the web store
open http://localhost:8080
```

### Step 4: Trigger Incidents

```bash
# The trigger script works with Kubernetes too
KUBE_CONTEXT=kind-incidentfox-lab ./incidentfox/scripts/trigger-incident.sh high-cpu

# Or manually edit the flagd configmap
kubectl edit configmap -n otel-demo flagd-config
```

### Step 5: Clean Up

```bash
# Delete the demo
kubectl delete -f kubernetes/opentelemetry-demo.yaml

# Delete the cluster
kind delete cluster --name incidentfox-lab
```

## Option 3: Kubernetes with k3d

### Step 1: Create k3d Cluster

```bash
# Create cluster with port forwarding
k3d cluster create incidentfox-lab \
  --port 8080:8080@loadbalancer \
  --port 9090:9090@loadbalancer

# Set context
kubectl config use-context k3d-incidentfox-lab
```

### Step 2: Deploy (same as kind)

```bash
kubectl apply -f kubernetes/opentelemetry-demo.yaml
kubectl wait --for=condition=ready pod --all -n otel-demo --timeout=300s
```

## Verifying the Installation

### 1. Check Service Health

```bash
# Docker Compose
curl http://localhost:8080
curl http://localhost:9090/-/healthy
curl http://localhost:16686/

# Kubernetes
kubectl get pods -n otel-demo
kubectl logs -n otel-demo -l app=frontend
```

### 2. Verify Metrics

```bash
# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=up'

# Should see all services with up=1
```

### 3. Verify Traces

```bash
# Check Jaeger for recent traces
curl 'http://localhost:16686/api/services'

# Should see: frontend, checkout, cart, etc.
```

### 4. Verify Logs

```bash
# Docker Compose
docker compose logs frontend | grep -i error

# Kubernetes
kubectl logs -n otel-demo -l app=frontend | grep -i error
```

## Troubleshooting

### Services Won't Start

```bash
# Check Docker resources
docker system df

# Clean up old containers/volumes
docker compose down -v
docker system prune -a

# Increase Docker Desktop memory to 8+ GB
```

### Port Conflicts

```bash
# Find what's using port 8080
lsof -i :8080

# Change the port in docker-compose.yml or use different ports
export ENVOY_PORT=8081
docker compose up -d
```

### Out of Memory

```bash
# Run minimal demo (fewer services)
docker compose -f docker-compose.minimal.yml up -d
```

### Kubernetes Pods Pending

```bash
# Check node resources
kubectl describe nodes

# Check pod events
kubectl describe pod -n otel-demo <pod-name>

# Reduce resource requests in manifests if needed
```

## Next Steps

- [Connect Your Agent](agent-integration.md)
- [Trigger Incidents](incident-scenarios.md)
- [Deploy to AWS](aws-deployment.md)

## Configuration

### Environment Variables

Key variables (see `.env` file in repo root):

```bash
# Ports
ENVOY_PORT=8080
PROMETHEUS_PORT=9090
JAEGER_UI_PORT=16686

# Load Generator
LOCUST_USERS=10
LOCUST_SPAWN_RATE=1
LOCUST_HEADLESS=false
LOCUST_AUTOSTART=true

# Feature Flags (for incidents)
# Edit src/flagd/demo.flagd.json
```

### Resource Limits

Docker Compose resource limits are set in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 300M
```

Adjust these if you have resource constraints.

## Development Tips

### Watch Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f frontend

# Filter by level
docker compose logs -f | grep ERROR
```

### Restart a Single Service

```bash
docker compose restart frontend
```

### Rebuild After Code Changes

```bash
# Rebuild specific service
docker compose up -d --build frontend

# Rebuild all
docker compose up -d --build
```

### Access Service Internals

```bash
# Shell into a container
docker compose exec frontend sh

# View service config
docker compose exec otel-collector cat /etc/otelcol-config.yml
```

