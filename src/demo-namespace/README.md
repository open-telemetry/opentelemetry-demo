# Demo Namespace

## Purpose

This directory defines the Kubernetes namespace where all Splunk Astronomy Shop services are deployed.

## What It Does

Creates the `astronomy-shop` namespace in your Kubernetes cluster, providing:

- **Isolation**: Separates demo resources from other workloads in the cluster
- **Organization**: Groups all related services under a single namespace
- **Easy Management**: Simplifies deployment, monitoring, and cleanup operations

## Namespace Name

**Current Namespace**: `astronomy-shop`

All services in this demo are deployed to this namespace.

## Usage

### Deploy the Namespace

```bash
kubectl apply -f src/demo-namespace/demo-namespace-k8s.yaml
```

### View Resources in the Namespace

```bash
# List all resources
kubectl get all -n astronomy-shop

# List pods
kubectl get pods -n astronomy-shop

# List services
kubectl get services -n astronomy-shop
```

### Delete the Namespace (and all resources)

```bash
# WARNING: This deletes everything in the namespace
kubectl delete namespace astronomy-shop
```

## Changing the Namespace Name

To use a different namespace name:

1. Edit `src/demo-namespace/demo-namespace-k8s.yaml`
2. Change `metadata.name` to your desired namespace
3. Update all service manifests to use the new namespace
4. Run the namespace addition script:
   ```bash
   python3 .github/scripts/add-namespace.py <new-namespace-name>
   ```

## Included in Manifest

This namespace definition is automatically included in the combined Kubernetes manifest:
- `kubernetes/splunk-astronomy-shop-<version>.yaml`

It is listed first in the manifest to ensure the namespace is created before any other resources.
