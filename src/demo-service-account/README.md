# Demo ServiceAccount

## Purpose

This directory defines the Kubernetes ServiceAccount used by all Splunk Astronomy Shop application pods.

## What It Does

Creates the `opentelemetry-demo` ServiceAccount that provides:

- **Pod Identity**: Gives all application pods a consistent identity within Kubernetes
- **RBAC Integration**: Enables role-based access control for pods
- **Service-to-Service Auth**: Supports authentication between microservices
- **API Access**: Controls which Kubernetes APIs the pods can access

## ServiceAccount Name

**Name**: `opentelemetry-demo`
**Namespace**: `astronomy-shop`

## Used By

This ServiceAccount is referenced by **23 application services** via:

```yaml
spec:
  template:
    spec:
      serviceAccountName: opentelemetry-demo
```

### Services Using This ServiceAccount

All application deployments including:
- accounting, ad, cart, checkout, currency, email
- fraud-detection, frontend, frontend-proxy, image-provider
- kafka, llm, payment, postgres, product-catalog
- product-reviews, quote, recommendation, shipping
- shop-dc-shim, valkey-cart, flagd, flagd-ui

## Usage

### Deploy the ServiceAccount

```bash
kubectl apply -f src/demo-service-account/demo-service-account-k8s.yaml
```

### View ServiceAccount Details

```bash
# View ServiceAccount
kubectl get serviceaccount opentelemetry-demo -n astronomy-shop

# Describe ServiceAccount
kubectl describe serviceaccount opentelemetry-demo -n astronomy-shop
```

### View Pods Using This ServiceAccount

```bash
kubectl get pods -n astronomy-shop \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.serviceAccountName}{"\n"}{end}'
```

## Security Considerations

The ServiceAccount is created with default permissions. For production deployments:

1. **Create RBAC Roles**: Define specific permissions needed by the application
2. **Bind Roles**: Use RoleBinding to grant permissions to this ServiceAccount
3. **Principle of Least Privilege**: Only grant permissions that are actually needed
4. **Separate ServiceAccounts**: Consider using different ServiceAccounts for services with different permission requirements

## Included in Manifest

This ServiceAccount definition is automatically included in the combined Kubernetes manifest:
- `kubernetes/splunk-astronomy-shop-<version>.yaml`

It appears after the namespace definition and before service deployments to ensure proper ordering.

## Modifying the ServiceAccount

If you rename this ServiceAccount, you must also update all service manifests that reference it:

```bash
# Search for references
grep -r "serviceAccountName: opentelemetry-demo" src/
```

Update each service's deployment to use the new ServiceAccount name.
