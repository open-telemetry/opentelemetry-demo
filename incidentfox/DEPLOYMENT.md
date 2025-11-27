# Deployment Guide - AWS Production Setup

Complete guide for deploying the IncidentFox lab to AWS EKS with production-grade secrets management.

## TL;DR

```bash
# One command deployment
cd incidentfox
./build-all.sh deploy
```

This idempotently:
1. Creates VPC with public/private subnets
2. Deploys EKS cluster with managed node groups
3. Sets up AWS Secrets Manager with generated passwords
4. Configures IRSA for External Secrets Operator
5. Deploys External Secrets Operator
6. Installs OpenTelemetry Demo via Helm
7. Syncs secrets from AWS to Kubernetes

## Architecture Overview

```
AWS Account
│
├── VPC (10.0.0.0/16)
│   ├── Public Subnets (2 AZs) - for ALB
│   ├── Private Subnets (2 AZs) - for EKS nodes
│   └── NAT Gateways - for egress
│
├── EKS Cluster
│   ├── Control Plane (managed by AWS)
│   ├── System Node Group (t3.medium × 2)
│   │   └── Monitoring, control plane components
│   └── Application Node Group (t3.large × 3)
│       └── OTel Demo services (15+ microservices)
│
├── AWS Secrets Manager
│   ├── incidentfox-demo/postgres
│   │   └── {username, password}
│   └── incidentfox-demo/grafana
│       └── {admin-user, admin-password}
│
├── IAM Roles (IRSA)
│   ├── External Secrets Operator
│   │   └── Read from Secrets Manager
│   └── ALB Controller
│       └── Manage Load Balancers
│
└── Application Load Balancer
    └── Routes traffic to demo services
```

## Prerequisites

**Required Tools:**
- AWS CLI v2+
- Terraform 1.5+
- kubectl 1.27+
- Helm 3.12+
- jq

**AWS Permissions:**
- VPC creation
- EKS cluster management
- IAM role/policy creation
- Secrets Manager
- EC2 instances

**Install:**
```bash
# macOS
brew install awscli terraform kubectl helm jq

# Configure AWS
aws configure --profile incidentfox
```

## Step-by-Step Deployment

### 1. Configure Variables

```bash
cd incidentfox/terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars
vim terraform.tfvars
```

Key settings:
```hcl
region      = "us-west-2"
cluster_name = "incidentfox-demo"
environment = "lab"

# Cost optimization: Use SPOT instances
app_node_capacity_type = "SPOT"  # 50-70% cheaper
app_node_desired_size  = 2        # Start small
```

### 2. Deploy Infrastructure

```bash
cd incidentfox
./build-all.sh deploy
```

Or manually:

```bash
cd terraform

# Initialize
terraform init

# Plan and apply
terraform plan -out=tfplan
terraform apply tfplan

# Note outputs
terraform output
```

### 3. Connect to Cluster

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --name incidentfox-demo \
  --region us-west-2

# Verify
kubectl get nodes
kubectl get pods -A
```

### 4. Wait for Services

```bash
# Watch pods start
watch kubectl get pods -n otel-demo

# All pods should reach Running state (5-10 minutes)
```

### 5. Access the Demo

```bash
# Get ALB DNS
kubectl get ingress -n otel-demo

# Access URLs:
# http://<ALB-DNS>/
# http://<ALB-DNS>/grafana
# http://<ALB-DNS>/jaeger/ui
```

## Secrets Management

### How It Works

See [secrets-management.md](docs/secrets-management.md) for complete details.

**TL;DR:**
1. Terraform creates secrets in AWS Secrets Manager with generated passwords
2. External Secrets Operator syncs them to Kubernetes
3. Applications consume standard Kubernetes secrets
4. No secrets in Git, Terraform state is encrypted, AWS manages rotation

### Accessing Secrets

```bash
# Via AWS CLI
aws secretsmanager get-secret-value \
  --secret-id incidentfox-demo/postgres | jq -r .SecretString

# Via kubectl
kubectl get secret postgres-credentials -n otel-demo \
  -o jsonpath='{.data.password}' | base64 -d
```

### Updating Secrets

```bash
# Update in AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id incidentfox-demo/postgres \
  --secret-string '{"username":"otelu","password":"newpass"}'

# External Secrets Operator will sync within 1 hour
# Or force immediate sync:
kubectl annotate externalsecret postgres-credentials \
  -n otel-demo \
  force-sync=$(date +%s) \
  --overwrite
```

## Cost Optimization

### Estimated Monthly Costs

| Resource | Configuration | Monthly Cost |
|----------|--------------|--------------|
| EKS Control Plane | - | $73 |
| System Nodes | t3.medium × 2 | ~$60 |
| App Nodes | t3.large × 3 | ~$190 |
| NAT Gateway | 1 | ~$32 |
| ALB | 1 | ~$16 |
| EBS Storage | 100 GB | ~$8 |
| Secrets Manager | 2 secrets | ~$1 |
| **Total** | | **~$380/month** |

### Cost Savings

**Use SPOT Instances** (50-70% savings):
```hcl
app_node_capacity_type = "SPOT"
```

**Reduce Node Count**:
```hcl
app_node_desired_size = 1
system_node_desired_size = 1
```

**Stop When Not in Use**:
```bash
# Scale down to 0
kubectl scale deployment --all --replicas=0 -n otel-demo

# Or delete node groups (preserves cluster)
aws eks update-nodegroup-config \
  --cluster-name incidentfox-demo \
  --nodegroup-name application \
  --scaling-config desiredSize=0,minSize=0,maxSize=10
```

**Use Single NAT Gateway** (automatic for dev environment):
```hcl
environment = "dev"  # Enables single_nat_gateway
```

## Monitoring & Operations

### Check Deployment Status

```bash
./build-all.sh status
```

### View Logs

```bash
# All pods
kubectl logs -n otel-demo --all-containers=true -l app=frontend

# Specific service
kubectl logs -n otel-demo -l app=payment --tail=100 -f

# External Secrets Operator
kubectl logs -n external-secrets-system \
  -l app.kubernetes.io/name=external-secrets -f
```

### Scaling

```bash
# Manual scale
kubectl scale deployment frontend -n otel-demo --replicas=3

# Add cluster autoscaler (production)
helm install cluster-autoscaler autoscaler/cluster-autoscaler \
  --set autoDiscovery.clusterName=incidentfox-demo
```

### Backup

```bash
# Export all manifests
kubectl get all,cm,secrets -n otel-demo -o yaml > backup.yaml

# Backup Prometheus data
kubectl exec -n otel-demo prometheus-0 -- tar czf - /prometheus \
  | tar xzf - -C ./backup/
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n otel-demo

# Common issues:
# 1. Insufficient resources → Scale up nodes
# 2. Image pull errors → Check ECR/registry permissions
# 3. Secret not found → Check ExternalSecret sync status
```

### ExternalSecret Not Syncing

```bash
# Check status
kubectl describe externalsecret postgres-credentials -n otel-demo

# Check operator logs
kubectl logs -n external-secrets-system \
  -l app.kubernetes.io/name=external-secrets

# Common issues:
# 1. IRSA role not configured → Check terraform output
# 2. Wrong secret name → Verify in AWS Secrets Manager
# 3. Permission denied → Check IAM policy
```

### ALB Not Creating

```bash
# Check ingress status
kubectl describe ingress -n otel-demo

# Check ALB controller logs
kubectl logs -n kube-system \
  -l app.kubernetes.io/name=aws-load-balancer-controller

# Common issues:
# 1. Subnet tags missing → Terraform should add them
# 2. IRSA role incorrect → Check annotations
# 3. Security group issues → Check VPC configuration
```

### High Costs

```bash
# Check what's running
kubectl top nodes
kubectl top pods -n otel-demo

# Identify expensive resources
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=SERVICE

# Scale down or use SPOT instances
```

## Cleanup

### Full Teardown

```bash
./build-all.sh destroy
```

This will:
1. Delete Helm releases
2. Delete Kubernetes namespaces
3. Wait for ALB/EBS to be deleted
4. Destroy EKS cluster
5. Destroy VPC and networking
6. Delete secrets from AWS Secrets Manager

**Warning:** This is irreversible! All data will be lost.

### Partial Cleanup

```bash
# Just the demo (keep cluster)
helm uninstall otel-demo -n otel-demo

# Just scale down (keep everything)
kubectl scale deployment --all --replicas=0 -n otel-demo
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to AWS

on:
  push:
    branches: [incidentfox]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-west-2
      
      - name: Deploy
        run: |
          cd incidentfox
          ./build-all.sh deploy
```

## Next Steps

1. **Set up monitoring**: Configure Grafana dashboards
2. **Enable alerting**: Connect to PagerDuty/Slack
3. **Connect agent**: Point IncidentFox agent at endpoints
4. **Trigger incidents**: Use `./scripts/trigger-incident.sh`
5. **Test automation**: Verify agent detects and remediates issues

## References

- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Secrets Management](docs/secrets-management.md)
- [Agent Integration](docs/agent-integration.md)
- [Incident Scenarios](docs/incident-scenarios.md)
- [Local Setup](docs/local-setup.md)

