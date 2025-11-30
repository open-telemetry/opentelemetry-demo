# IncidentFox Code Walkthrough

Complete guide to understanding everything we built for the IncidentFox lab environment.

---

## 📁 Directory Structure Overview

```
incidentfox/
├── README.md                          # Main entry point
├── DEPLOYMENT.md                      # AWS deployment guide
├── DEPLOYMENT-STATUS.md               # Current deployment status
├── CODE-WALKTHROUGH.md               # This file
│
├── docs/                              # Documentation
│   ├── local-setup.md                # Docker/k8s local setup
│   ├── agent-integration.md          # How to connect AI agent
│   ├── incident-scenarios.md         # Catalog of failure scenarios
│   ├── aws-deployment.md             # AWS/EKS deployment details
│   ├── secrets-management.md         # Secrets architecture
│   └── SECRETS-EXPLAINED.md          # What secrets exist and where
│
├── scripts/                           # Automation scripts
│   ├── build-all.sh                  # Master deployment script
│   ├── trigger-incident.sh           # Master incident trigger
│   ├── export-secrets-to-1password.sh # Export secrets for backup
│   ├── scenarios/                    # Individual incident scripts
│   │   ├── high-cpu.sh
│   │   ├── memory-leak.sh
│   │   ├── service-failure.sh
│   │   └── ... (12 total)
│   └── load/                         # Load generation scripts
│       ├── normal-load.sh
│       └── spike-load.sh
│
├── agent-config/                      # Agent configuration
│   ├── endpoints.yaml                # All observability endpoints
│   └── example-config.yaml           # Full agent config template
│
├── terraform/                         # AWS infrastructure code
│   ├── main.tf                       # Main configuration
│   ├── variables.tf                  # Input variables
│   ├── versions.tf                   # Provider versions
│   ├── terraform.tfvars              # Your customizations (not in Git)
│   ├── terraform.tfvars.example      # Example file
│   └── modules/                      # Reusable modules
│       ├── vpc/                      # VPC with public/private subnets
│       ├── eks/                      # EKS cluster and node groups
│       ├── secrets/                  # AWS Secrets Manager
│       └── irsa/                     # IAM Roles for Service Accounts
│
└── helm/                              # Kubernetes deployment
    ├── README.md
    ├── values-aws.yaml               # AWS-specific settings
    ├── values-aws-simple.yaml        # Simplified (currently used)
    └── values-incidentfox.yaml       # IncidentFox customizations
```

---

## 🎯 High-Level Architecture

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

---

## 🔑 Key Components Explained

### 1. **scripts/build-all.sh** - The Master Script

**Purpose:** One-command deployment of everything

**What it does:**
1. Checks prerequisites (aws, terraform, kubectl, helm, jq)
2. Deploys infrastructure via Terraform
3. Configures kubectl to connect to cluster
4. Deploys External Secrets Operator (optional)
5. Creates SecretStore and ExternalSecrets
6. Deploys OpenTelemetry Demo via Helm
7. Shows status and access URLs

**Usage:**
```bash
./scripts/build-all.sh deploy    # Deploy everything
./scripts/build-all.sh destroy   # Teardown everything
./scripts/build-all.sh status    # Check status
```

**Key sections:**
- `check_prerequisites()` - Validates tools installed
- `deploy_infrastructure()` - Runs Terraform
- `deploy_otel_demo()` - Runs Helm install
- `show_status()` - Displays current state

---

### 2. **terraform/** - Infrastructure as Code

#### **main.tf** - Main Configuration

**Purpose:** Orchestrates all infrastructure modules

**Key resources:**
```hcl
# VPC with public/private subnets
module "vpc" {
  source = "./modules/vpc"
  cidr = "10.0.0.0/16"
  azs  = ["us-west-2a", "us-west-2b"]
}

# EKS cluster with 2 node groups
module "eks" {
  source = "./modules/eks"
  node_groups = {
    system = { ... }      # For monitoring/control plane
    application = { ... }  # For demo services
  }
}

# Secrets with random passwords
resource "random_password" "postgres" {
  length  = 32
  special = true
}

module "secrets" {
  secrets = {
    postgres = {
      secret_data = {
        username = "otelu"
        password = random_password.postgres.result  # ← Random!
      }
    }
  }
}

# IRSA roles for External Secrets and ALB Controller
module "external_secrets_irsa" { ... }
module "alb_controller_irsa" { ... }
```

**Flow:**
1. Random passwords generated
2. VPC created
3. EKS cluster created
4. Node groups launched
5. Secrets stored in AWS Secrets Manager
6. IRSA roles created for secure access

---

#### **modules/vpc/** - Network Foundation

**Purpose:** Creates isolated network with public/private subnets

**What it creates:**
```
VPC (10.0.0.0/16)
├── Public Subnets (2 AZs)
│   ├── 10.0.0.0/20 (us-west-2a)
│   └── 10.0.16.0/20 (us-west-2b)
│   └── → Internet Gateway
│
└── Private Subnets (2 AZs)
    ├── 10.0.32.0/20 (us-west-2a)
    ├── 10.0.48.0/20 (us-west-2b)
    └── → NAT Gateways (one per AZ)
```

**Key components:**
- `aws_vpc` - The VPC itself
- `aws_internet_gateway` - For public subnet internet access
- `aws_nat_gateway` - For private subnet egress
- `aws_route_table` - Routing rules
- **Tags** - EKS-specific tags for subnet discovery

---

#### **modules/eks/** - Kubernetes Cluster

**Purpose:** Creates managed Kubernetes cluster

**What it creates:**
- EKS control plane (managed by AWS)
- IAM roles (cluster role, node role)
- OIDC provider for IRSA
- 2 managed node groups:
  - **System:** 2-6 nodes for monitoring
  - **Application:** 4-12 nodes for services
- Cluster add-ons:
  - VPC CNI (networking)
  - CoreDNS (DNS)
  - Kube-proxy (networking)
  - EBS CSI Driver (persistent storage)

**Key resources:**
```hcl
resource "aws_eks_cluster" "main" {
  name    = "incidentfox-demo"
  version = "1.28"
  # ... 10-15 minutes to create
}

resource "aws_eks_node_group" "main" {
  # Creates EC2 Auto Scaling Group
  # Nodes join cluster automatically
}
```

---

#### **modules/secrets/** - Password Management

**Purpose:** Store secrets in AWS Secrets Manager

**What it does:**
```hcl
resource "aws_secretsmanager_secret" "main" {
  name = "incidentfox-demo/postgres"
}

resource "aws_secretsmanager_secret_version" "main" {
  secret_id     = aws_secretsmanager_secret.main.id
  secret_string = jsonencode({
    username = "otelu"
    password = random_password.postgres.result
  })
}
```

**Security:**
- Encrypted at rest
- Access controlled by IAM
- Audit via CloudTrail
- Rotation supported

---

#### **modules/irsa/** - IAM Roles for Service Accounts

**Purpose:** Allow Kubernetes pods to assume AWS IAM roles

**How it works:**
```
1. EKS creates OIDC provider
2. IAM role trusts OIDC provider
3. Kubernetes ServiceAccount annotated with role ARN
4. Pod uses ServiceAccount
5. Pod gets temporary AWS credentials
6. No long-lived keys needed!
```

**Example:**
```hcl
# Trust relationship
data "aws_iam_policy_document" "assume_role" {
  statement {
    principals {
      type = "Federated"
      identifiers = [oidc_provider_arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test = "StringEquals"
      variable = "...sub"
      values = ["system:serviceaccount:namespace:sa-name"]
    }
  }
}
```

**Used by:**
- External Secrets Operator (reads Secrets Manager)
- ALB Controller (manages load balancers)

---

### 3. **scripts/trigger-incident.sh** - Incident Simulation

**Purpose:** Unified interface to trigger all 12 incident scenarios

**How it works:**
1. Reads feature flag config: `src/flagd/demo.flagd.json`
2. Modifies the `defaultVariant` field
3. flagd auto-reloads config (5-10 seconds)
4. Services detect flag change and alter behavior

**Example:**
```bash
./trigger-incident.sh high-cpu
```

**Under the hood:**
```bash
# Changes this in demo.flagd.json:
{
  "adHighCpu": {
    "defaultVariant": "off"  → "on"
  }
}

# Ad service periodically checks flag
# When "on", triggers CPU-intensive loop
```

**12 scenarios:**
- `high-cpu` - Ad service CPU spike
- `memory-leak` - Email service memory leak
- `service-failure` - Payment failures (10-100%)
- `service-unreachable` - Payment goes offline
- `latency-spike` - Image loading delays (5-10 sec)
- `kafka-lag` - Message queue backlog
- `cache-failure` - Recommendation cache fails
- `catalog-failure` - Product catalog errors
- `ad-gc-pressure` - Java GC pauses
- `traffic-spike` - Load generator flood
- `llm-inaccuracy` - AI returns wrong data
- `llm-rate-limit` - AI rate limit errors

---

### 4. **agent-config/** - Agent Configuration

#### **endpoints.yaml** - Observability Endpoints Reference

**Purpose:** Documents every endpoint your agent needs

**Structure:**
```yaml
docker_compose:      # For local development
  prometheus:
    query_api: "http://localhost:9090/api/v1"
  jaeger:
    query_api: "http://localhost:16686/api"
  
kubernetes_in_cluster:   # For agent running in cluster
  prometheus:
    query_api: "http://prometheus.otel-demo.svc.cluster.local:9090/api/v1"
  
aws_eks_ingress:         # For agent outside cluster
  prometheus:
    query_api: "http://<ALB-DNS>/prometheus/api/v1"

# Also includes example queries
prometheus_queries:
  service_up: "up{job=~\".*\"}"
  error_rate: "sum(rate(...)) by (service_name)"
```

---

#### **example-config.yaml** - Full Agent Config

**Purpose:** Complete reference configuration for your agent

**Key sections:**

**1. Datasources:**
```yaml
datasources:
  metrics:
    type: "prometheus"
    endpoint: "http://localhost:9090"
    query_api: "http://localhost:9090/api/v1"
  
  traces:
    type: "jaeger"
    endpoint: "http://localhost:16686"
  
  logs:
    type: "opensearch"
    endpoint: "http://localhost:9200"
```

**2. Detection Rules:**
```yaml
detection:
  key_metrics:
    - name: "service_up"
      query: "up{job=~\".*\"}"
      threshold:
        operator: "=="
        value: 0
      severity: "critical"
    
    - name: "error_rate"
      query: "sum(rate(http_server_requests_total{...}[5m]))"
      threshold:
        operator: ">"
        value: 0.05  # 5% error rate
      severity: "high"
```

**3. Remediation:**
```yaml
remediation:
  actions:
    modify_feature_flags:
      enabled: true
      endpoint: "http://localhost:8080/feature"
      allowed_operations: ["disable"]
    
    restart_services:
      enabled: false  # Dangerous
```

---

### 5. **Secrets Management Architecture**

#### The Two-Tier System

**Tier 1: AWS Secrets Manager (Source of Truth)**
```
Terraform creates:
  random_password → AWS Secrets Manager
                    (encrypted, audited, centralized)
```

**Tier 2: External Secrets Operator (Sync to k8s)**
```
ExternalSecret → Reads from AWS (via IRSA)
               → Creates Kubernetes Secret
               → Pods consume as env vars
```

#### **Why This Approach?**

**Traditional (BAD):**
```yaml
# Hardcoded in Git
env:
  - name: DB_PASSWORD
    value: "password123"  # ❌ NEVER DO THIS
```

**Our Approach (GOOD):**
```hcl
# Terraform generates random password
resource "random_password" "postgres" {
  length = 32  # Secure, unique
}

# Stores in AWS Secrets Manager
resource "aws_secretsmanager_secret_version" "main" {
  secret_string = jsonencode({
    password = random_password.postgres.result
  })
}
```

**Then pods consume:**
```yaml
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgres-credentials
        key: password
```

**Benefits:**
- ✅ No secrets in Git
- ✅ Randomly generated
- ✅ Centralized in AWS
- ✅ Automatic sync to k8s
- ✅ IRSA for secure access (no access keys)

---

## 🔍 Deep Dive: How Secrets Flow

### Step-by-Step Secret Lifecycle

**1. Terraform Generates Password (on your laptop)**
```hcl
resource "random_password" "postgres" {
  length  = 32
  special = true
}
# Result: "YVsU&=5K2cpXP>P-wxS9}*6LG4z9:@KB"
```

**2. Terraform Stores in AWS**
```hcl
module "secrets" {
  secrets = {
    postgres = {
      secret_data = {
        username = "otelu"
        password = random_password.postgres.result
      }
    }
  }
}
```

Creates in AWS Secrets Manager:
```
ARN: arn:aws:secretsmanager:us-west-2:...:secret:incidentfox-demo/postgres-MJKO8E
Value: {"username":"otelu","password":"YVsU&=5K2cpXP>P-wxS9}*6LG4z9:@KB"}
```

**3. IRSA Role Created**
```hcl
module "external_secrets_irsa" {
  policy_statements = [{
    effect = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:*:*:secret:incidentfox-demo/*"]
  }]
}
```

Creates IAM role that:
- Can only read secrets with prefix `incidentfox-demo/*`
- Can be assumed by ServiceAccount `external-secrets-sa`
- Uses temporary credentials (refreshed automatically)

**4. External Secrets Operator Syncs**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgres-credentials
spec:
  refreshInterval: 1h
  data:
    - secretKey: password
      remoteRef:
        key: incidentfox-demo/postgres
        property: password
```

Operator:
1. Assumes IRSA role (gets temp AWS creds)
2. Calls `secretsmanager:GetSecretValue`
3. Creates k8s Secret `postgres-credentials`
4. Refreshes every hour

**5. PostgreSQL Pod Consumes**
```yaml
spec:
  containers:
    - name: postgres
      env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: password
```

**6. You Can Export Anytime**
```bash
./scripts/export-secrets-to-1password.sh
```

Reads from AWS Secrets Manager (source of truth) and exports to JSON/CSV.

---

## 🚀 Deployment Flow Explained

### What Happens When You Run `./scripts/build-all.sh deploy`

**Phase 1: Prerequisites (10 seconds)**
```bash
✓ Check aws cli installed
✓ Check terraform installed
✓ Check kubectl installed
✓ Check helm installed
✓ Check jq installed
✓ Verify AWS credentials valid
```

**Phase 2: Terraform Infrastructure (15-20 minutes)**
```bash
terraform init          # Download providers
terraform plan          # Preview changes
terraform apply         # Create resources

Creates:
  ✓ VPC (13 seconds)
  ✓ Subnets (2 seconds)
  ✓ NAT Gateways (90 seconds)
  ✓ EKS Cluster (10 minutes) ← Longest step
  ✓ Node Groups (2-3 minutes)
  ✓ Secrets in AWS Secrets Manager (1 second)
  ✓ IAM Roles for IRSA (1 second)
```

**Phase 3: Kubernetes Setup (1 minute)**
```bash
aws eks update-kubeconfig  # Configure kubectl
kubectl get nodes          # Verify connection
```

**Phase 4: External Secrets (2-5 minutes)**
```bash
helm install external-secrets  # Deploy operator
kubectl apply SecretStore      # Configure AWS connection
kubectl apply ExternalSecret   # Sync secrets
```

**Phase 5: OpenTelemetry Demo (10-15 minutes)**
```bash
helm install otel-demo         # Deploy 25 services
kubectl wait pods              # Wait for all Ready
```

**Phase 6: LoadBalancers (3-5 minutes)**
```bash
AWS provisions NLBs
DNS propagates
```

**Total: ~30-40 minutes**

---

## 📝 Incident Scenarios Explained

### How Feature Flags Work

**Architecture:**
```
flagd service (runs in cluster)
  ↓ watches file
src/flagd/demo.flagd.json
  ↓ contains
{
  "adHighCpu": {
    "defaultVariant": "off",  ← This is what we change
    "variants": {
      "on": true,
      "off": false
    }
  }
}
```

**Services check flags:**
```python
# In ad service (simplified)
from openfeature import api

client = api.get_client()
high_cpu_enabled = client.get_boolean_value("adHighCpu", False)

if high_cpu_enabled:
    # Trigger CPU-intensive loop
    while True:
        compute_intensive_operation()
```

**Triggering:**
```bash
# Our script changes the JSON file
./scripts/trigger-incident.sh high-cpu

# Which runs:
jq '.flags.adHighCpu.defaultVariant = "on"' demo.flagd.json > tmp
mv tmp demo.flagd.json

# flagd detects file change (5-10 sec)
# Services re-fetch flag values
# Behavior changes!
```

---

## 🔧 Key Configuration Files

### **terraform.tfvars** - Your Customizations

**What's in it:**
```hcl
# NO SECRETS! Only infrastructure config

region = "us-west-2"
cluster_name = "incidentfox-demo"

# Instance types
system_node_instance_type = "t3.small"
app_node_instance_type    = "t3.small"

# Node counts
system_node_desired_size = 2
app_node_desired_size    = 6

# Tags
tags = {
  Project = "incidentfox"
  Owner   = "playground-admin"
}
```

**NOT in Git** because:
- Contains your AWS account specifics
- May have custom tags with team names
- But NO passwords (those are in AWS Secrets Manager)

---

### **helm/values-aws-simple.yaml** - Kubernetes Config

**What it does:**
```yaml
# Adjust memory for t3.small nodes
components:
  loadGenerator:
    resources:
      limits:
        memory: 800Mi  # Was 1500Mi, too much for t3.small
```

**Customizes:**
- Resource limits per service
- LoadBalancer type (NLB)
- Storage class (EBS gp3)

---

## 🎓 Understanding IRSA (IAM Roles for Service Accounts)

### The Problem

**Old way (BAD):**
```yaml
# Store AWS credentials in k8s secret
apiVersion: v1
kind: Secret
data:
  access_key: base64(AKIAIOSFODNN7EXAMPLE)
  secret_key: base64(wJalrXUtnFEMI/K7MDENG/...)
  
# Pod uses these credentials
# Problems:
# - Long-lived credentials
# - Hard to rotate
# - Broad permissions
# - Insecure
```

**New way (GOOD) - IRSA:**
```yaml
# ServiceAccount with annotation
apiVersion: v1
kind: ServiceAccount
metadata:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::...:role/my-role

# Pod uses ServiceAccount
# Gets temporary credentials automatically!
# No secrets needed!
```

### How IRSA Works

```
1. Pod starts with ServiceAccount
2. AWS injects webhook token (JWT)
3. Pod calls AWS STS AssumeRoleWithWebIdentity
4. STS verifies JWT with EKS OIDC provider
5. STS returns temporary credentials (15min-1hr)
6. Pod uses credentials to access AWS services
7. Credentials refresh automatically
```

**Security benefits:**
- ✅ No long-lived keys
- ✅ Automatic rotation
- ✅ Fine-grained permissions per pod
- ✅ Audit via CloudTrail

---

## 📊 Infrastructure Components Summary

### AWS Resources (45 total)

**Network (15):**
- 1 VPC
- 2 Public subnets
- 2 Private subnets
- 1 Internet Gateway
- 2 NAT Gateways
- 2 Elastic IPs
- 3 Route tables
- 4 Route table associations

**Compute (11):**
- 1 EKS cluster
- 2 Node groups
- 8 EC2 instances (nodes)

**IAM (8):**
- 2 IAM roles (cluster, nodes)
- 4 Policy attachments
- 1 OIDC provider
- 1 IRSA role (external-secrets)

**Secrets (4):**
- 2 Secrets in Secrets Manager
- 2 Secret versions

**Add-ons (4):**
- VPC CNI
- CoreDNS
- Kube-proxy
- EBS CSI Driver

**Load Balancers (3):**
- Frontend NLB
- Prometheus NLB
- Grafana NLB

---

### Kubernetes Resources (100+)

**Namespaces (2):**
- `otel-demo` - Demo services
- `external-secrets-system` - Secrets operator

**Deployments (24):**
- 15 microservices
- 6 observability components
- 3 infrastructure services

**StatefulSets (1):**
- OpenSearch

**Services (26):**
- 23 ClusterIP services
- 3 LoadBalancer services

**ConfigMaps (10+):**
- Feature flags
- Grafana dashboards
- Prometheus config
- OTel Collector config

**Pods (57):**
- 25 application pods
- 32 system pods

---

## 🎯 Critical Files to Understand

### 1. **build-all.sh** (497 lines)
Master orchestration script - calls Terraform and Helm in sequence

### 2. **terraform/main.tf** (400+ lines)
Orchestrates all infrastructure modules

### 3. **terraform/modules/vpc/main.tf** (150 lines)
Network foundation - subnets, NAT, routes

### 4. **terraform/modules/eks/main.tf** (200 lines)
EKS cluster, nodes, IAM roles

### 5. **terraform/modules/irsa/main.tf** (80 lines)
IRSA roles for secure AWS access

### 6. **terraform/modules/secrets/main.tf** (20 lines)
AWS Secrets Manager integration

### 7. **trigger-incident.sh** (237 lines)
Incident simulation controller

---

## 💡 Design Decisions Explained

### Why VPC with Public/Private Subnets?

**Public subnets:**
- Load Balancers need public IPs
- Internet Gateway provides access

**Private subnets:**
- EKS nodes don't need public IPs
- More secure (not directly accessible)
- NAT Gateway for outbound (pull images, call APIs)

**Multi-AZ:**
- High availability
- If one AZ fails, other continues

---

### Why Two Node Groups?

**System nodes (t3.small × 2):**
- CoreDNS, kube-proxy
- Monitoring pods
- Control plane components
- Stable, predictable load

**Application nodes (t3.small × 6):**
- Demo microservices
- Can scale independently
- Can use SPOT instances (future)
- Isolates application from system

---

### Why t3.small Instead of Larger?

**Originally planned:** t3.xlarge (4 vCPU, 16GB)

**AWS restriction:** Account limited to Free Tier eligible instances

**Solution:** t3.small (2 vCPU, 2GB) with MORE nodes
- 6 application nodes = 12 vCPU, 12GB total
- Better distribution anyway!
- More resilient (workload spread)

---

### Why External Secrets Operator?

**Without ESO:**
```bash
# Manual process:
1. Create secret in AWS
2. Copy password
3. Create k8s secret manually
4. If password changes, repeat steps 2-3
```

**With ESO:**
```bash
# Automatic process:
1. Create secret in AWS (via Terraform)
2. ESO syncs automatically
3. If password changes in AWS, ESO updates k8s (within 1hr)
```

**Benefits:**
- Single source of truth (AWS)
- No manual k8s secret management
- Automatic rotation support
- Audit trail in CloudTrail

---

## 🎯 Design Principles

**1. Separation of Concerns**
- Infrastructure (Terraform) vs Application (Helm)
- System nodes vs Application nodes
- Public vs Private subnets

**2. Security by Default**
- No secrets in Git
- IRSA over long-lived credentials
- Private subnets for workloads
- Least privilege IAM policies

**3. High Availability**
- Multi-AZ deployment
- Multiple NAT Gateways
- Distributed node placement
- Pod anti-affinity rules

**4. Upstream Compatibility**
- All customizations in `incidentfox/` directory
- Minimal changes to demo code
- Easy to rebase from upstream

---

## 📚 Files You Should Review

### **Essential (Must Read):**

1. **README.md** - Overview and quick start
2. **DEPLOYMENT-STATUS.md** - Current deployment info
3. **docs/SECRETS-EXPLAINED.md** - Secret management explained
4. **scripts/build-all.sh** - Master deployment script

### **Important (Should Read):**

5. **terraform/main.tf** - Infrastructure orchestration
6. **terraform/modules/*/main.tf** - Module implementations
7. **docs/agent-integration.md** - Agent connection guide
8. **docs/incident-scenarios.md** - Scenario catalog

### **Reference (Read as Needed):**

9. **agent-config/endpoints.yaml** - All endpoints documented
10. **agent-config/example-config.yaml** - Agent config template

---

---

## Further Reading

- [AWS Deployment Guide](aws-deployment.md) - Deployment steps, operations, troubleshooting
- [Secrets Management](secrets.md) - Complete secrets guide
- [Agent Integration](agent-integration.md) - Connect your AI agent
- [Incident Scenarios](incident-scenarios.md) - Test failures

