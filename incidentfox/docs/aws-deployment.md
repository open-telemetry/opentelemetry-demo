# AWS Deployment Guide

Complete guide for deploying the IncidentFox lab to AWS EKS with production-grade infrastructure.

## Quick Start

```bash
# One command deployment
cd incidentfox
./scripts/build-all.sh deploy
```

This deploys:
- VPC with public/private subnets
- EKS cluster with managed node groups  
- AWS Secrets Manager with generated passwords
- OpenTelemetry Demo (25 microservices)
- LoadBalancers for external access

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                          AWS Account                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    EKS Cluster                          │ │
│  │                                                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │ │
│  │  │  OTel Demo  │  │   Metrics   │  │    Logs     │    │ │
│  │  │  Services   │  │ (Prometheus)│  │ (OpenSearch)│    │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘    │ │
│  │                                                          │ │
│  │  ┌─────────────┐  ┌─────────────┐                      │ │
│  │  │   Traces    │  │  Dashboards │                      │ │
│  │  │  (Jaeger)   │  │  (Grafana)  │                      │ │
│  │  └─────────────┘  └─────────────┘                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  Supporting Services                    │ │
│  │                                                          │ │
│  │  • VPC with public/private subnets                      │ │
│  │  • ALB for ingress                                      │ │
│  │  • EBS CSI driver for persistent storage               │ │
│  │  • IAM roles and policies                               │ │
│  │  • CloudWatch for cluster logs                          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
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
- Secrets Manager access
- EC2 instance management

**Install:**
```bash
# macOS
brew install awscli terraform kubectl helm jq

# Configure AWS
aws configure --profile playground
export AWS_PROFILE=playground
```

## Deployment Steps

### Option 1: Automated (Recommended)

```bash
cd incidentfox

# Configure (first time only)
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
cd ..

# Deploy everything
./scripts/build-all.sh deploy
```

### Option 2: Manual

```bash
# 1. Deploy infrastructure
cd incidentfox/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 2. Configure kubectl
aws eks update-kubeconfig --name incidentfox-demo --region us-west-2

# 3. Deploy demo
cd ../helm
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm upgrade --install otel-demo open-telemetry/opentelemetry-demo \
  --namespace otel-demo \
  --create-namespace \
  --wait

# 4. Expose services
kubectl patch svc frontend-proxy -n otel-demo -p '{"spec":{"type":"LoadBalancer"}}'
kubectl patch svc prometheus -n otel-demo -p '{"spec":{"type":"LoadBalancer"}}'
kubectl patch svc grafana -n otel-demo -p '{"spec":{"type":"LoadBalancer"}}'
```

## What Gets Deployed

### AWS Resources (45 total)

**Network (15):**
- 1 VPC (10.0.0.0/16)
- 2 Public subnets (for LoadBalancers)
- 2 Private subnets (for EKS nodes)
- 1 Internet Gateway
- 2 NAT Gateways
- 2 Elastic IPs
- 3 Route tables
- 4 Route table associations

**Compute (11):**
- 1 EKS cluster (Kubernetes 1.28)
- 2 Node groups (system + application)
- 8 EC2 instances (t3.small)

**IAM (8):**
- 2 IAM roles (cluster, nodes)
- 4 Policy attachments
- 1 OIDC provider
- 1 IRSA role (external-secrets)

**Secrets (4):**
- 2 Secrets in AWS Secrets Manager
- 2 Secret versions (with random passwords)

**Add-ons (4):**
- VPC CNI (networking)
- CoreDNS (DNS)
- Kube-proxy (service routing)
- EBS CSI Driver (persistent storage)

**Load Balancers (3):**
- Frontend NLB
- Prometheus NLB
- Grafana NLB

### Kubernetes Resources (100+)

**Services (25 pods):**
- 11 E-commerce services (frontend, cart, checkout, etc.)
- 3 Backend services (accounting, fraud-detection, image-provider)
- 4 Infrastructure (kafka, postgresql, valkey, flagd)
- 6 Observability (prometheus, jaeger, grafana, opensearch, collector, load-generator)
- 1 Proxy (envoy)

**System Components (32 pods):**
- VPC CNI (8 daemonset pods)
- EBS CSI (2 controllers + 8 node pods)
- Kube-proxy (8 daemonset pods)
- CoreDNS (2 replicas)
- External Secrets (3 pods)

## Terraform Structure (Planned)

```
incidentfox/terraform/
├── main.tf                  # Main configuration
├── variables.tf             # Input variables
├── outputs.tf               # Outputs (cluster name, endpoint, etc.)
├── versions.tf              # Provider versions
├── vpc.tf                   # VPC configuration
├── eks.tf                   # EKS cluster
├── iam.tf                   # IAM roles and policies
├── alb.tf                   # ALB controller
├── ebs-csi.tf              # EBS CSI driver
├── terraform.tfvars.example # Example variables
└── README.md               # Terraform-specific docs
```

## Helm Chart Customization (Planned)

```
incidentfox/helm/
├── opentelemetry-demo/
│   ├── Chart.yaml
│   ├── values.yaml          # Default values
│   ├── values-aws.yaml      # AWS-specific overrides
│   ├── templates/
│   │   ├── ingress.yaml
│   │   ├── servicemonitor.yaml
│   │   └── ...
│   └── README.md
└── README.md
```

## Cost Estimation

Estimated monthly costs for running the demo 24/7:

| Resource | Type | Cost/Month |
|----------|------|------------|
| EKS Control Plane | - | $73 |
| EC2 Instances | t3.large × 3 | ~$190 |
| NAT Gateway | 1 × 24/7 | ~$32 |
| ALB | 1 × standard | ~$16 |
| EBS Storage | 100 GB gp3 | ~$8 |
| Data Transfer | ~10 GB/month | ~$1 |
| **Total** | | **~$320/month** |

**Cost Optimization Tips:**
- Use Spot instances for app nodes (50-70% savings)
- Stop the cluster during off-hours
- Use smaller instance types for testing
- Enable cluster autoscaler

## Security Considerations

### Network Security

- Private subnets for all workloads
- Security groups restricting traffic
- No direct internet access from pods (via NAT)

### IAM Security

- Principle of least privilege
- IRSA for pod-level IAM roles
- No long-lived credentials in pods

### Secrets Management

- AWS Secrets Manager (optional)
- Kubernetes secrets for demo credentials
- Encrypt etcd at rest

### Monitoring

- CloudWatch Container Insights
- VPC Flow Logs
- ALB Access Logs

## Deployment Steps (Detailed)

### 1. Prepare AWS Environment

```bash
# Set AWS credentials
export AWS_PROFILE=incidentfox
export AWS_REGION=us-west-2

# Verify access
aws sts get-caller-identity
```

### 2. Deploy Infrastructure with Terraform

```bash
cd incidentfox/terraform

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
cluster_name = "incidentfox-demo"
region = "us-west-2"
cluster_version = "1.28"

# Node groups
system_node_instance_type = "t3.medium"
system_node_desired_size = 2
app_node_instance_type = "t3.large"
app_node_desired_size = 3
app_node_max_size = 10

# Networking
vpc_cidr = "10.0.0.0/16"

# Tags
tags = {
  Environment = "lab"
  Project     = "incidentfox"
  ManagedBy   = "terraform"
}
EOF

# Initialize and deploy
terraform init
terraform plan
terraform apply
```

### 3. Configure kubectl

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --name incidentfox-demo \
  --region us-west-2

# Verify connection
kubectl get nodes
kubectl get namespaces
```

### 4. Deploy Demo via Helm

```bash
cd incidentfox/helm

# Add necessary Helm repos (if using upstream)
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# Deploy with AWS-specific values
helm install otel-demo ./opentelemetry-demo \
  --namespace otel-demo \
  --create-namespace \
  --values values-aws.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod --all -n otel-demo --timeout=600s
```

### 5. Configure Ingress

```bash
# Get ALB DNS name
kubectl get ingress -n otel-demo

# Create DNS record (optional)
# Point demo.incidentfox.io → ALB DNS name
```

### 6. Verify Deployment

```bash
# Check all pods
kubectl get pods -n otel-demo

# Test connectivity
curl http://<alb-dns-name>/

# Access UIs (via port-forward initially)
kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080
kubectl port-forward -n otel-demo svc/prometheus 9090:9090
```

## Accessing the Demo

### Via Port Forwarding (Development)

```bash
# Frontend
kubectl port-forward -n otel-demo svc/frontend-proxy 8080:8080

# Prometheus
kubectl port-forward -n otel-demo svc/prometheus 9090:9090

# Grafana
kubectl port-forward -n otel-demo svc/grafana 3000:80

# Jaeger
kubectl port-forward -n otel-demo svc/jaeger-query 16686:16686
```

### Via ALB Ingress (Production)

Access via the ALB DNS name or your custom domain:

- **Frontend:** http://demo.incidentfox.io/
- **Grafana:** http://demo.incidentfox.io/grafana
- **Jaeger:** http://demo.incidentfox.io/jaeger/ui

## Monitoring the Infrastructure

### EKS Cluster

```bash
# Cluster info
kubectl cluster-info

# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -n otel-demo
```

### CloudWatch Insights (Optional)

```bash
# Enable Container Insights
aws eks update-cluster-config \
  --name incidentfox-demo \
  --region us-west-2 \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}'
```

### AWS Console

- **EKS:** View cluster status, nodes, workloads
- **EC2:** Monitor instance health
- **CloudWatch:** View logs and metrics
- **Cost Explorer:** Track spending

## Scaling

### Manual Scaling

```bash
# Scale node group
aws eks update-nodegroup-config \
  --cluster-name incidentfox-demo \
  --nodegroup-name app-nodes \
  --scaling-config desiredSize=5

# Scale deployments
kubectl scale deployment -n otel-demo frontend --replicas=3
```

### Cluster Autoscaler (Coming Soon)

Will automatically scale node groups based on pod resource requests.

### Horizontal Pod Autoscaler

```bash
# Scale based on CPU
kubectl autoscale deployment frontend \
  --namespace otel-demo \
  --cpu-percent=70 \
  --min=2 \
  --max=10
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod -n otel-demo <pod-name>

# Check events
kubectl get events -n otel-demo --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n otel-demo <pod-name>
```

### Can't Access Services

```bash
# Check service endpoints
kubectl get svc -n otel-demo

# Check ingress
kubectl describe ingress -n otel-demo

# Check ALB Controller logs
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
```

### High Costs

```bash
# Review resources
kubectl get pods -n otel-demo -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].resources}{"\n"}{end}'

# Enable Spot instances in Terraform
# Scale down when not in use
terraform apply -var="app_node_desired_size=1"
```

## Cleanup

### Delete Demo

```bash
# Delete Helm release
helm uninstall otel-demo -n otel-demo

# Delete namespace
kubectl delete namespace otel-demo
```

### Delete Infrastructure

```bash
cd incidentfox/terraform

# Destroy all resources
terraform destroy

# Confirm deletion
aws eks list-clusters
```

**Important:** Ensure all LoadBalancers and EBS volumes are deleted to avoid lingering costs.

## Next Steps

- [ ] Implement Terraform modules
- [ ] Create Helm chart with AWS optimizations
- [ ] Add CI/CD pipeline for automated deployments
- [ ] Set up monitoring and alerting
- [ ] Document backup and disaster recovery procedures
- [ ] Add cost optimization features (Spot, autoscaling)

## Resources

- [Amazon EKS User Guide](https://docs.aws.amazon.com/eks/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Helm Documentation](https://helm.sh/docs/)
- [AWS ALB Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)

