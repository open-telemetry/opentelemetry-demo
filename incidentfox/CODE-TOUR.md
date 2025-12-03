# IncidentFox Code Tour - 2 Hour Deep Dive

Complete walkthrough of the codebase in logical order. Budget: 2 hours.

---

## 🎯 Tour Structure

**Part 1 (20 min):** Big picture - what we built  
**Part 2 (40 min):** Infrastructure - Terraform deep dive  
**Part 3 (30 min):** Secrets management - complete flow  
**Part 4 (20 min):** Deployment automation - build-all.sh  
**Part 5 (10 min):** Incident system - feature flags

---

# Part 1: The Big Picture (20 minutes)

## What We Built - Three Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: AWS Infrastructure (Terraform)                     │
│  • VPC, subnets, NAT, Internet Gateway                      │
│  • EKS cluster, node groups                                 │
│  • AWS Secrets Manager                                      │
│  • IAM roles (IRSA)                                         │
│  • LoadBalancers                                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Kubernetes Resources (Helm)                        │
│  • 25 microservice deployments                              │
│  • Services (ClusterIP + LoadBalancer)                      │
│  • ConfigMaps (feature flags, configs)                      │
│  • Secrets (synced from AWS)                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Control & Testing (Scripts)                        │
│  • build-all.sh - Deploy everything                         │
│  • trigger-incident.sh - Inject failures                    │
│  • export-secrets-to-1password.sh - Backup                  │
└─────────────────────────────────────────────────────────────┘
```

## The Core Innovation: Secrets Management

**Traditional (BAD):**
```
hardcoded password → committed to Git → security nightmare
```

**Our Approach (GOOD):**
```
Terraform generates random password
    ↓
Stores in AWS Secrets Manager (encrypted)
    ↓
External Secrets Operator syncs to Kubernetes (via IRSA)
    ↓
Pods consume as environment variables
    ↓
You can export to 1Password anytime
```

**No secrets in Git, ever!**

---

# Part 2: Infrastructure Code (40 minutes)

Let's walk through the Terraform code that creates everything.

## 2.1 Entry Point: `terraform/main.tf`

**Open:** `incidentfox/terraform/main.tf`

### Structure Overview

```hcl
# Line 1-10: Comments explaining what this deploys

# Line 12-50: Provider configuration
provider "aws" {
  region = var.region  # From terraform.tfvars
  
  default_tags {       # All resources get these tags
    tags = {
      Environment = var.environment
      Project     = "incidentfox"
      ManagedBy   = "terraform"
    }
  }
}

# Line 52-60: Data sources (read-only queries to AWS)
data "aws_availability_zones" "available" {
  state = "available"  # Get available AZs in region
}

data "aws_caller_identity" "current" {
  # Who am I? Returns account ID, user ARN
}

# Line 62-65: Local variables (computed values)
locals {
  cluster_name   = var.cluster_name
  azs            = slice(data.aws_availability_zones.available.names, 0, 2)
  # Takes first 2 AZs: ["us-west-2a", "us-west-2b"]
}

# Line 67-120: VPC Module
module "vpc" {
  source = "./modules/vpc"
  # ... calls vpc module
}

# Line 122-230: EKS Module  
module "eks" {
  source = "./modules/eks"
  # ... calls eks module
}

# Line 232-270: Secrets Module
resource "random_password" "postgres" { ... }
resource "random_password" "grafana" { ... }
module "secrets" { ... }

# Line 272-330: IRSA Modules
module "external_secrets_irsa" { ... }
module "alb_controller_irsa" { ... }

# Line 332-400: Outputs (what to display after apply)
output "vpc_id" { ... }
output "cluster_endpoint" { ... }
output "secrets" { ... }
```

### Key Concept: Modules

Think of modules as **functions** in Terraform:

```hcl
# Calling a module
module "vpc" {
  source = "./modules/vpc"  # Which "function" to call
  
  # Arguments (inputs)
  name = "incidentfox-demo-vpc"
  cidr = "10.0.0.0/16"
  azs  = ["us-west-2a", "us-west-2b"]
  
  # Returns (outputs)
  # vpc_id, public_subnets, private_subnets
}

# Using module outputs
module "eks" {
  vpc_id = module.vpc.vpc_id  # Reference output from vpc module
}
```

---

## 2.2 VPC Module: `terraform/modules/vpc/main.tf`

**Open:** `incidentfox/terraform/modules/vpc/main.tf`

### What It Creates (In Order)

**1. VPC (lines 3-16)**
```hcl
resource "aws_vpc" "main" {
  cidr_block           = var.cidr  # 10.0.0.0/16
  enable_dns_hostnames = true      # Nodes get DNS names
  enable_dns_support   = true      # DNS resolution works
  
  tags = {
    Name = "incidentfox-demo-vpc"
  }
}
```

**2. Internet Gateway (lines 18-28)**
```hcl
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id  # Attach to our VPC
  
  # This allows public subnets to access internet
}
```

**3. Public Subnets (lines 30-45)**
```hcl
resource "aws_subnet" "public" {
  count = 2  # Create 2 subnets
  
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnets[count.index]
  # [0] = 10.0.0.0/20
  # [1] = 10.0.16.0/20
  
  availability_zone = var.azs[count.index]
  # [0] = us-west-2a
  # [1] = us-west-2b
  
  map_public_ip_on_launch = true  # Instances get public IPs
  
  tags = {
    Name = "incidentfox-demo-vpc-public-us-west-2a"  # (for count=0)
    "kubernetes.io/role/elb" = "1"  # ← EKS LoadBalancer discovery tag
  }
}
```

**Why this tag matters:** When you create a LoadBalancer Service in Kubernetes, AWS Load Balancer Controller scans subnets for this tag to know where to place the LoadBalancer.

**4. Private Subnets (lines 47-64)**
```hcl
resource "aws_subnet" "private" {
  count = 2
  
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnets[count.index]
  # [0] = 10.0.32.0/20
  # [1] = 10.0.48.0/20
  
  availability_zone = var.azs[count.index]
  # map_public_ip_on_launch = false (default, not public)
  
  tags = {
    "kubernetes.io/role/internal-elb" = "1"  # Internal LBs go here
  }
}
```

**5. NAT Gateways (lines 66-95)**
```hcl
# First, allocate Elastic IPs (public IPs)
resource "aws_eip" "nat" {
  count = 2  # One per AZ
  domain = "vpc"
  
  depends_on = [aws_internet_gateway.main]  # Need IGW first
}

# Then create NAT Gateways
resource "aws_nat_gateway" "main" {
  count = 2
  
  allocation_id = aws_eip.nat[count.index].id     # The public IP
  subnet_id     = aws_subnet.public[count.index].id  # Goes in PUBLIC subnet!
  
  # NAT needs to be in public subnet to access internet
}
```

**Key insight:** NAT Gateway lives in PUBLIC subnet but serves PRIVATE subnet.

**6. Route Tables (lines 97-140)**

**Public route:**
```hcl
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block = "0.0.0.0/0"  # All internet traffic
    gateway_id = aws_internet_gateway.main.id  # Goes through IGW
  }
}

# Associate with public subnets
resource "aws_route_table_association" "public" {
  count = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
```

**Private routes:**
```hcl
resource "aws_route_table" "private" {
  count = 2  # One per AZ
  
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block     = "0.0.0.0/0"  # All internet traffic
    nat_gateway_id = aws_nat_gateway.main[count.index].id  # Through NAT
  }
}

# Associate with private subnets
resource "aws_route_table_association" "private" {
  count = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
```

**The routing:**
```
Public subnet instance:
  Internet → via Internet Gateway (bidirectional)

Private subnet instance:
  Internet → via NAT Gateway → via Internet Gateway (outbound only)
```

---

## 2.3 EKS Module: `terraform/modules/eks/main.tf`

**Open:** `incidentfox/terraform/modules/eks/main.tf`

### IAM Roles First

**Cluster Role (lines 3-30):**
```hcl
# Trust policy: "AWS EKS service can assume this role"
data "aws_iam_policy_document" "cluster_assume_role" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]  # EKS service
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "cluster" {
  name               = "incidentfox-demo-cluster-role"
  assume_role_policy = data.aws_iam_policy_document.cluster_assume_role.json
}

# Attach AWS-managed policies
resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}
```

**What AmazonEKSClusterPolicy allows:**
- Create/manage ENIs (network interfaces)
- Assign security groups
- Manage ELBs
- Describe VPC resources

**Node Role (lines 58-95):**
```hcl
resource "aws_iam_role" "node" {
  name = "incidentfox-demo-node-role"
  # Nodes (EC2 instances) assume this role
}

# Attach multiple policies
resource "aws_iam_role_policy_attachment" "node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  # Allows nodes to connect to EKS
}

resource "aws_iam_role_policy_attachment" "node_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  # Allows VPC CNI to assign IPs to pods
}

resource "aws_iam_role_policy_attachment" "node_ebs_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  # Allows attaching EBS volumes to pods
}
```

### EKS Cluster (lines 32-56)

```hcl
resource "aws_eks_cluster" "main" {
  name     = "incidentfox-demo"
  version  = "1.28"
  role_arn = aws_iam_role.cluster.arn  # Use role we created
  
  vpc_config {
    subnet_ids = var.subnet_ids  # Private subnets from VPC module
    endpoint_private_access = true   # Nodes can access control plane
    endpoint_public_access  = true   # We can access via kubectl
  }
  
  enabled_cluster_log_types = ["api", "audit", ...]  # CloudWatch logs
  
  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy  # Wait for permissions
  ]
}
```

**This takes 10-15 minutes** because AWS:
1. Provisions control plane VMs (hidden from you)
2. Sets up API server, etcd, scheduler
3. Configures networking
4. Enables logging

### OIDC Provider (lines 58-75)

```hcl
# Get TLS certificate from EKS OIDC endpoint
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
  # Fetches cert from: https://oidc.eks.us-west-2.amazonaws.com/id/304AD825...
}

# Register OIDC provider with AWS IAM
resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]  # Who can use tokens
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}
```

**What this does:**
- Tells AWS IAM: "Trust JWT tokens from this EKS cluster"
- Enables IRSA (pods can assume IAM roles)
- Foundation for secure secrets access

### Node Groups (lines 97-155)

```hcl
resource "aws_eks_node_group" "main" {
  for_each = var.node_groups  # Loop over node_groups map
  
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "incidentfox-demo-${each.key}"  # e.g., "...-system"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids  # Spread across private subnets
  
  capacity_type  = each.value.capacity_type  # ON_DEMAND or SPOT
  instance_types = each.value.instance_types  # ["t3.small"]
  
  scaling_config {
    desired_size = each.value.desired_size  # 2 or 6
    min_size     = each.value.min_size
    max_size     = each.value.max_size
  }
  
  labels = each.value.labels  # Kubernetes labels
  # e.g., {role: "system"} or {role: "application"}
}
```

**What `for_each` does:**
```hcl
# In main.tf, we pass:
node_groups = {
  system = {
    desired_size = 2
    instance_types = ["t3.small"]
    labels = {role = "system"}
  }
  application = {
    desired_size = 6
    instance_types = ["t3.small"]
    labels = {role = "application"}
  }
}

# Creates 2 node groups from this map
```

### Cluster Add-ons (lines 157-170)

```hcl
resource "aws_eks_addon" "main" {
  for_each = var.cluster_addons
  
  cluster_name = aws_eks_cluster.main.name
  addon_name   = each.key  # "coredns", "vpc-cni", etc.
  
  addon_version = each.value.most_recent ? null : each.value.version
  # most_recent = true means "use latest available"
  
  resolve_conflicts_on_update = "PRESERVE"
  # Don't overwrite manual changes
}
```

**What gets installed:**
- `coredns` - DNS for service discovery
- `kube-proxy` - Service routing
- `vpc-cni` - Pod networking (VPC IPs)
- `aws-ebs-csi-driver` - Persistent volumes

---

## 2.4 Secrets Module: `terraform/modules/secrets/main.tf`

**Open:** `incidentfox/terraform/modules/secrets/main.tf`

**This is surprisingly simple** (only 20 lines):

```hcl
# Create secret container
resource "aws_secretsmanager_secret" "main" {
  for_each = var.secrets  # Loop over secrets map
  
  name        = "${var.secrets_prefix}/${each.key}"
  # Result: "incidentfox-demo/postgres"
  
  description = each.value.description
  
  tags = var.tags
}

# Store actual secret value
resource "aws_secretsmanager_secret_version" "main" {
  for_each = var.secrets
  
  secret_id     = aws_secretsmanager_secret.main[each.key].id
  secret_string = jsonencode(each.value.secret_data)
  # Converts {username: "otelu", password: "xyz"} to JSON string
}
```

**How it's called from main.tf:**
```hcl
module "secrets" {
  source = "./modules/secrets"
  
  secrets_prefix = "incidentfox-demo"
  
  secrets = {
    postgres = {
      description = "PostgreSQL credentials"
      secret_data = {
        username = "otelu"
        password = random_password.postgres.result  # ← Random!
      }
    }
    grafana = {
      description = "Grafana credentials"
      secret_data = {
        admin-user     = "admin"
        admin-password = random_password.grafana.result  # ← Random!
      }
    }
  }
}
```

**Result in AWS:**
```
Secret: incidentfox-demo/postgres
ARN: arn:aws:secretsmanager:us-west-2:103002841599:secret:incidentfox-demo/postgres-MJKO8E
Value: {"username":"otelu","password":"YVsU&=5K2cpXP>P-wxS9}*6LG4z9:@KB"}
```

---

## 2.5 IRSA Module: `terraform/modules/irsa/main.tf`

**Open:** `incidentfox/terraform/modules/irsa/main.tf`

This is the most complex but most important security feature.

### The Trust Policy (lines 3-30)

```hcl
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"
    
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
      # arn:aws:iam::...:oidc-provider/oidc.eks...amazonaws.com/id/304AD825...
    }
    
    actions = ["sts:AssumeRoleWithWebIdentity"]
    
    # CRITICAL: Only allow specific ServiceAccount
    condition {
      test     = "StringEquals"
      variable = "${replace(oidc_provider_arn, "/^(.*provider/)/", "")}:sub"
      # Becomes: "oidc.eks.us-west-2.amazonaws.com/id/304AD825...:sub"
      
      values = ["system:serviceaccount:${var.namespace}:${var.service_account_name}"]
      # e.g., "system:serviceaccount:external-secrets-system:external-secrets-sa"
    }
    
    condition {
      test     = "StringEquals"
      variable = "${...}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}
```

**What this says:**
```
"Allow JWT tokens from my EKS OIDC provider to assume this role,
 BUT ONLY IF:
 1. The 'sub' claim equals 'system:serviceaccount:external-secrets-system:external-secrets-sa'
 2. The 'aud' claim equals 'sts.amazonaws.com'"
```

**Why two conditions:**
- `sub` check: Ensures only specific ServiceAccount
- `aud` check: Ensures token intended for AWS STS (not other services)

### The IAM Role (lines 32-45)

```hcl
resource "aws_iam_role" "main" {
  name               = var.role_name
  # "incidentfox-demo-external-secrets"
  
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  # Use trust policy from above
}
```

### The Permissions Policy (lines 47-70)

```hcl
data "aws_iam_policy_document" "main" {
  dynamic "statement" {
    for_each = var.policy_statements  # Loop over statements
    
    content {
      effect    = statement.value.effect    # "Allow"
      actions   = statement.value.actions   # ["secretsmanager:GetSecretValue"]
      resources = statement.value.resources # ["arn:...secret:incidentfox-demo/*"]
    }
  }
}

resource "aws_iam_policy" "main" {
  name   = "${var.role_name}-policy"
  policy = data.aws_iam_policy_document.main.json
}

resource "aws_iam_role_policy_attachment" "main" {
  role       = aws_iam_role.main.name
  policy_arn = aws_iam_policy.main.arn
}
```

### How It's Used (from main.tf)

```hcl
module "external_secrets_irsa" {
  source = "./modules/irsa"
  
  cluster_name         = "incidentfox-demo"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  namespace            = "external-secrets-system"
  service_account_name = "external-secrets-sa"
  role_name            = "incidentfox-demo-external-secrets"
  
  policy_statements = [
    {
      effect = "Allow"
      actions = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
      ]
      resources = [
        "arn:aws:secretsmanager:us-west-2:103002841599:secret:incidentfox-demo/*"
      ]
    }
  ]
}
```

**Result:**
- Role: `incidentfox-demo-external-secrets`
- Can be assumed by: Only pods using `external-secrets-sa` ServiceAccount
- Permissions: Read secrets with prefix `incidentfox-demo/*`
- Nothing else!

---

# Part 3: Secrets Management Flow (30 minutes)

## 3.1 The Complete Journey of a Password

Let me trace **one password** from generation to consumption.

### Step 1: Terraform Generates (main.tf lines 232-237)

```hcl
resource "random_password" "postgres" {
  length  = 32
  special = true
}
```

**What happens:**
- Terraform uses cryptographically secure random generator
- Generates: `YVsU&=5K2cpXP>P-wxS9}*6LG4z9:@KB`
- Stores in Terraform state (terraform.tfstate)

**Run terraform apply:**
```bash
$ terraform apply
random_password.postgres: Creating...
random_password.postgres: Creation complete after 0s [id=none]
```

### Step 2: Terraform Stores in AWS (main.tf lines 239-258)

```hcl
module "secrets" {
  secrets = {
    postgres = {
      secret_data = {
        username = "otelu"
        password = random_password.postgres.result  # References the random pw
      }
    }
  }
}
```

**What happens:**
```bash
$ terraform apply
module.secrets.aws_secretsmanager_secret.main["postgres"]: Creating...
module.secrets.aws_secretsmanager_secret.main["postgres"]: Created
  ARN: arn:aws:secretsmanager:us-west-2:103002841599:secret:incidentfox-demo/postgres-MJKO8E

module.secrets.aws_secretsmanager_secret_version.main["postgres"]: Creating...
  Value: {"username":"otelu","password":"YVsU&=5K2cpXP>P-wxS9}*6LG4z9:@KB"}
module.secrets.aws_secretsmanager_secret_version.main["postgres"]: Created
```

**Now in AWS Secrets Manager:**
- Encrypted at rest
- Access logged in CloudTrail
- Can be retrieved by anything with IAM permission

### Step 3: IRSA Role Created (main.tf lines 260-282)

```hcl
module "external_secrets_irsa" {
  # Creates IAM role that can read secrets
  policy_statements = [{
    effect = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:*:*:secret:incidentfox-demo/*"]
  }]
}
```

**Output:**
```bash
$ terraform output external_secrets_role_arn
arn:aws:iam::103002841599:role/incidentfox-demo-external-secrets
```

### Step 4: External Secrets Operator Deployed (build-all.sh)

**Code:** `scripts/build-all.sh` lines 165-180

```bash
deploy_external_secrets() {
  helm repo add external-secrets https://charts.external-secrets.io
  
  helm upgrade --install external-secrets \
    external-secrets/external-secrets \
    --namespace external-secrets-system \
    --create-namespace
}
```

**Creates pods:**
```bash
$ kubectl get pods -n external-secrets-system
NAME                              READY   STATUS
external-secrets-5bf4bff568-xxx   1/1     Running
external-secrets-webhook-xxx      1/1     Running
```

### Step 5: SecretStore Created (build-all.sh lines 195-210)

```bash
kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: otel-demo
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa  # Uses IRSA!
EOF
```

**What this does:**
- Tells External Secrets Operator: "Use AWS Secrets Manager"
- Authentication: IRSA via `external-secrets-sa`
- Scope: Can access secrets in us-west-2

### Step 6: ExternalSecret Created (build-all.sh lines 212-240)

```bash
kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgres-credentials
  namespace: otel-demo
spec:
  refreshInterval: 1h  # Re-sync every hour
  
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  
  target:
    name: postgres-credentials  # Name of k8s secret to create
    creationPolicy: Owner       # ESO owns this secret
  
  data:
    - secretKey: password       # Key in k8s secret
      remoteRef:
        key: incidentfox-demo/postgres  # AWS secret name
        property: password                # JSON property
    
    - secretKey: username
      remoteRef:
        key: incidentfox-demo/postgres
        property: username
EOF
```

**What External Secrets Operator does:**

1. **Reads ExternalSecret resource**
2. **Assumes IAM role** via IRSA:
   ```
   - Reads JWT from /var/run/secrets/eks.amazonaws.com/serviceaccount/token
   - Calls: aws sts assume-role-with-web-identity
   - Gets temporary credentials
   ```
3. **Calls AWS Secrets Manager:**
   ```
   aws secretsmanager get-secret-value --secret-id incidentfox-demo/postgres
   ```
4. **Parses JSON response:**
   ```json
   {"username": "otelu", "password": "YVsU&=5K..."}
   ```
5. **Creates Kubernetes Secret:**
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: postgres-credentials
   data:
     username: b3RlbHU=  # base64("otelu")
     password: WVZzVS... # base64("YVsU&=5K...")
   ```
6. **Refreshes every hour** (refreshInterval: 1h)

### Step 7: PostgreSQL Pod Consumes

**In Helm chart (simplified):**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgresql
spec:
  template:
    spec:
      containers:
        - name: postgres
          image: postgres:16
          env:
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-credentials  # ← The secret ESO created
                  key: password
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: postgres-credentials
                  key: username
```

**When pod starts:**
1. Kubernetes injects environment variables
2. `POSTGRES_PASSWORD=YVsU&=5K2cpXP>P-wxS9}*6LG4z9:@KB`
3. PostgreSQL uses this to set admin password
4. Other services connect with this password

### Step 8: You Can Export Anytime

**Code:** `scripts/export-secrets-to-1password.sh` lines 50-90

```bash
# Read from AWS (source of truth)
secret_value=$(aws secretsmanager get-secret-value \
  --secret-id incidentfox-demo/postgres \
  --query SecretString \
  --output text)

# Parse JSON
echo "$secret_value" | jq .
# {"username":"otelu","password":"YVsU&=5K2cpXP>P-wxS9}*6LG4z9:@KB"}

# Export to JSON file
# Export to 1Password CSV
```

---

## 3.2 Security Properties

**At no point are secrets:**
- ❌ Hardcoded in code
- ❌ Committed to Git
- ❌ Stored in config files
- ❌ Passed as command-line arguments
- ❌ Accessible without proper IAM permissions

**Secrets flow through:**
- ✅ Terraform state (encrypted if S3 backend)
- ✅ AWS Secrets Manager (encrypted at rest)
- ✅ Kubernetes secrets (base64, not encrypted but RBAC protected)
- ✅ Pod environment variables (ephemeral, pod lifetime only)

**Access control:**
- Terraform: Your AWS credentials
- AWS Secrets Manager: IAM policies
- External Secrets Operator: IRSA role (temporary credentials)
- Kubernetes secrets: RBAC (ServiceAccounts)
- Pods: Can only see secrets in their namespace

---

# Part 4: Deployment Automation (20 minutes)

## 4.1 Master Script: `scripts/build-all.sh`

**Open:** `incidentfox/scripts/build-all.sh`

### Structure

```bash
# Lines 1-30: Configuration and setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${INCIDENTFOX_ROOT}/terraform"
HELM_DIR="${INCIDENTFOX_ROOT}/helm"

AWS_REGION="${AWS_REGION:-us-west-2}"
CLUSTER_NAME="${CLUSTER_NAME:-incidentfox-demo}"

# Lines 32-50: Logging functions
log_info()    # Blue  [INFO]
log_success() # Green [SUCCESS]
log_warning() # Yellow [WARNING]
log_error()   # Red   [ERROR]

# Lines 52-84: check_prerequisites()
# Lines 86-130: deploy_infrastructure()
# Lines 132-150: update_kubeconfig()
# Lines 152-180: deploy_external_secrets()
# Lines 182-245: configure_secrets()
# Lines 247-290: deploy_otel_demo()
# Lines 292-350: show_status()
# Lines 352-380: destroy_all()
# Lines 382-450: deploy_all() - main orchestration
```

### Key Function: deploy_infrastructure()

```bash
deploy_infrastructure() {
  log_info "Deploying infrastructure with Terraform..."
  
  cd "$TERRAFORM_DIR"
  
  # Initialize Terraform (idempotent - safe to run multiple times)
  terraform init -upgrade
  
  # Check if terraform.tfvars exists
  if [ ! -f terraform.tfvars ]; then
    log_error "terraform.tfvars not found"
    log_info "Copy terraform.tfvars.example and customize"
    exit 1
  fi
  
  # Plan changes
  terraform plan -out=tfplan
  
  # Apply (idempotent)
  terraform apply tfplan
  
  # Clean up plan file
  rm -f tfplan
  
  # Export outputs for later use
  export VPC_ID=$(terraform output -raw vpc_id)
  export CLUSTER_NAME=$(terraform output -raw cluster_name)
}
```

**Idempotent means:**
- Safe to run multiple times
- Only creates what doesn't exist
- Updates what changed
- Doesn't duplicate resources

### Key Function: deploy_otel_demo()

```bash
deploy_otel_demo() {
  cd "$HELM_DIR"
  
  # Create namespace (idempotent)
  kubectl create namespace otel-demo --dry-run=client -o yaml | kubectl apply -f -
  
  # Add Helm repo
  helm repo add open-telemetry https://...
  helm repo update
  
  # Install/upgrade (idempotent)
  helm upgrade --install otel-demo open-telemetry/opentelemetry-demo \
    --namespace otel-demo \
    --values values-aws-simple.yaml \
    --wait \
    --timeout 15m
}
```

**`helm upgrade --install`:**
- If doesn't exist: install
- If exists: upgrade
- Idempotent!

---

## 4.2 Variables: `terraform/terraform.tfvars`

**Open:** `incidentfox/terraform/terraform.tfvars`

**Current values:**
```hcl
region      = "us-west-2"
environment = "lab"
cluster_name = "incidentfox-demo"
cluster_version = "1.28"

vpc_cidr = "10.0.0.0/16"

# Node configuration
system_node_instance_type = "t3.small"
system_node_desired_size  = 2

app_node_instance_type = "t3.small"
app_node_desired_size  = 6
app_node_capacity_type = "ON_DEMAND"

tags = {
  Project = "incidentfox"
  Owner   = "playground-admin"
}
```

**How it flows:**
```
terraform.tfvars → variables.tf (declarations) → main.tf (usage) → modules
```

**Example:**
```hcl
# terraform.tfvars
app_node_desired_size = 6

# variables.tf
variable "app_node_desired_size" {
  description = "Desired number of application nodes"
  type        = number
}

# main.tf
module "eks" {
  node_groups = {
    application = {
      desired_size = var.app_node_desired_size  # = 6
    }
  }
}

# modules/eks/main.tf
resource "aws_eks_node_group" "main" {
  scaling_config {
    desired_size = each.value.desired_size  # = 6
  }
}
```

---

# Part 5: Incident System (10 minutes)

## 5.1 Feature Flag Configuration

**File:** `src/flagd/demo.flagd.json` (upstream, we don't modify)

**Structure:**
```json
{
  "flags": {
    "adHighCpu": {
      "defaultVariant": "off",
      "description": "Triggers high cpu load in the ad service",
      "state": "ENABLED",
      "variants": {
        "on": true,
        "off": false
      }
    },
    "paymentFailure": {
      "defaultVariant": "off",
      "state": "ENABLED",
      "variants": {
        "100%": 1,
        "50%": 0.5,
        "off": 0
      }
    }
  }
}
```

**Key fields:**
- `defaultVariant`: Which variant is currently active (we change this!)
- `variants`: Possible values
- `state`: ENABLED means flag is active

## 5.2 Trigger Script: `scripts/trigger-incident.sh`

**Open:** `incidentfox/scripts/trigger-incident.sh`

### Main Logic (lines 150-175)

```bash
trigger_scenario() {
  local scenario="$1"  # e.g., "high-cpu"
  
  # Map scenario to script
  local script="${SCENARIOS_DIR}/${scenario}.sh"
  
  if [ ! -f "$script" ]; then
    print_error "Unknown scenario: $scenario"
    return 1
  fi
  
  # Execute the scenario script
  "$script" "${@:2}"  # Pass remaining args
}
```

### Individual Scenario: `scripts/scenarios/high-cpu.sh`

**Open:** `incidentfox/scripts/scenarios/high-cpu.sh`

```bash
#!/bin/bash
# Lines 1-8: Setup
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"
FLAG_NAME="adHighCpu"

# Lines 10-15: Enable the flag
cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"  # Backup first

jq ".flags.${FLAG_NAME}.defaultVariant = \"on\"" "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"

# Lines 17-25: Print expected behavior
echo "✓ Flag 'adHighCpu' set to 'on'"
echo "Expected: CPU usage will spike to 80-100%"
```

**What `jq` does:**
```bash
# Before:
{
  "flags": {
    "adHighCpu": {
      "defaultVariant": "off"
    }
  }
}

# After:
{
  "flags": {
    "adHighCpu": {
      "defaultVariant": "on"  ← Changed!
    }
  }
}
```

### How Services React

**In ad service code (Java - simplified):**
```java
import dev.openfeature.sdk.Client;

Client client = OpenFeatureAPI.getInstance().getClient();

while (true) {
  boolean highCpuEnabled = client.getBooleanValue("adHighCpu", false);
  
  if (highCpuEnabled) {
    // Trigger CPU-intensive operation
    for (int i = 0; i < 1000000; i++) {
      Math.sqrt(i);  // Burn CPU
    }
  }
  
  // Normal ad serving logic
  serveAd();
}
```

**flagd watches the file:**
- Detects file change within 5-10 seconds
- Services poll flagd every few seconds
- New flag value returned
- Service behavior changes!

---

# Part 6: Understanding the Deployed System (20 minutes)

## 6.1 What's Actually Running

### Check Current State

```bash
# Nodes
$ kubectl get nodes
# 8 nodes, t3.small, across 2 AZs

# Pods
$ kubectl get pods -n otel-demo
# 25 pods running

# Services
$ kubectl get svc -n otel-demo
# 23 ClusterIP + 4 LoadBalancer
```

### Network Flow

```
User Browser
  ↓ HTTP
LoadBalancer (NLB)
  ↓
frontend-proxy (Envoy) - Pod IP: 10.0.x.x
  ↓
frontend (Next.js) - Pod IP: 10.0.y.y
  ↓
product-catalog (Go) - Pod IP: 10.0.z.z
```

**All pod IPs are from VPC CIDR** (10.0.0.0/16) thanks to VPC CNI!

### Service Discovery

```bash
# In frontend pod:
$ curl http://product-catalog:8080/products

# How this works:
1. Pod DNS resolver → CoreDNS (172.20.0.10)
2. CoreDNS queries k8s API: "What's product-catalog service?"
3. Returns ClusterIP: 172.20.96.254
4. Pod connects to ClusterIP
5. kube-proxy intercepts via iptables
6. Rewrites to actual pod IP: 10.0.46.123:8080
7. Request arrives at product-catalog pod
```

---

## 6.2 Data Flow: A Request Journey

Let's trace a **user buying a product**:

**1. User clicks "Buy" in browser**
```
Browser → LoadBalancer (NLB)
  DNS: a06d7f5e0e0c949aebbaba8fb471d596-1428151517.us-west-2.elb.amazonaws.com
```

**2. LoadBalancer routes to frontend-proxy**
```
NLB → frontend-proxy pod (Envoy)
  Envoy terminates connection
  Envoy route: /checkout → checkout service
```

**3. Checkout service processes order**
```go
// checkout/main.go (simplified)
func processCheckout(ctx context.Context, req *CheckoutRequest) {
  // 1. Call cart service to get items
  cart := cartClient.GetCart(ctx, req.UserId)
  
  // 2. Call payment service
  payment := paymentClient.Charge(ctx, cart.Total)
  
  // 3. Call shipping service
  shipping := shippingClient.Ship(ctx, req.Address)
  
  // 4. Send to Kafka
  kafka.Produce("orders", order)
  
  return &CheckoutResponse{OrderId: orderId}
}
```

**4. Kafka message consumed by accounting**
```csharp
// accounting/Consumer.cs (simplified)
consumer.Subscribe("orders");

while (true) {
  var message = consumer.Consume();
  var order = JsonSerializer.Deserialize<Order>(message.Value);
  
  // Write to PostgreSQL
  dbContext.Orders.Add(order);
  dbContext.SaveChanges();  // ← Data persisted!
}
```

**5. Order saved to PostgreSQL**
```sql
INSERT INTO orders (order_id, user_id, total, timestamp)
VALUES ('abc-123', 'user-456', 99.99, NOW());
```

**Throughout all this:**
- OpenTelemetry collects traces (distributed tracing)
- Prometheus scrapes metrics (request counts, latencies)
- Logs sent to OpenSearch (errors, info)

---

## 6.3 Observability Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Pods                          │
│  frontend, checkout, payment, etc.                          │
│                                                              │
│  • Instrumented with OpenTelemetry SDKs                     │
│  • Export: metrics, logs, traces                            │
└──────────────────────────┬──────────────────────────────────┘
                           │ OTLP protocol
                           ↓
┌──────────────────────────────────────────────────────────────┐
│              OTel Collector (aggregation)                    │
│  • Receives from all services                                │
│  • Processes, filters, enriches                              │
│  • Routes to backends                                        │
└────┬──────────────┬──────────────┬──────────────────────────┘
     │              │              │
     ↓              ↓              ↓
┌─────────┐  ┌──────────┐  ┌────────────┐
│Prometheus│  │  Jaeger  │  │ OpenSearch │
│ (metrics)│  │ (traces) │  │   (logs)   │
└─────────┘  └──────────┘  └────────────┘
     ↓              ↓              ↓
     └──────────────┴──────────────┘
                    │
                    ↓
            ┌──────────────┐
            │   Grafana    │
            │ (dashboards) │
            └──────────────┘
```

---

# Part 7: Key Takeaways

## What You Should Remember

### 1. Infrastructure Stack
```
VPC → EKS → Nodes → Pods → Services → LoadBalancers
```

### 2. Secret Flow
```
Terraform random_password
  → AWS Secrets Manager
  → External Secrets (via IRSA)
  → Kubernetes Secret
  → Pod env vars
```

### 3. Network Design
- **Public subnets:** LoadBalancers (Internet Gateway for bidirectional)
- **Private subnets:** EKS nodes (NAT Gateway for outbound only)
- **Multi-AZ:** 2 zones for high availability

### 4. Security
- **IRSA:** No long-lived AWS credentials
- **OIDC:** JWT-based authentication
- **Secrets Manager:** Centralized, encrypted
- **No secrets in Git:** Ever!

### 5. Idempotence
- `terraform apply` - Creates what's missing, updates what changed
- `helm upgrade --install` - Installs or upgrades
- `kubectl apply` - Creates or updates
- `build-all.sh deploy` - Can run anytime, safe

---

# Part 8: Practical Exercises

## Exercise 1: Trace a Secret (5 min)

```bash
# 1. See it in AWS
aws secretsmanager get-secret-value \
  --secret-id incidentfox-demo/postgres \
  --region us-west-2

# 2. See the IRSA role
aws iam get-role \
  --role-name incidentfox-demo-external-secrets

# 3. See ExternalSecret
kubectl get externalsecret postgres-credentials -n otel-demo -o yaml

# 4. See resulting k8s Secret
kubectl get secret postgres-credentials -n otel-demo -o yaml

# 5. See pod using it
kubectl get deployment postgresql -n otel-demo -o yaml | grep -A 5 "POSTGRES_PASSWORD"
```

## Exercise 2: Trigger an Incident (5 min)

```bash
cd incidentfox

# Trigger high CPU
./scripts/trigger-incident.sh high-cpu

# Watch metrics
open "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/graph?g0.expr=rate(process_cpu_seconds_total%7Bservice_name%3D%22ad%22%7D%5B1m%5D)"

# Clear
./scripts/trigger-incident.sh clear-all
```

## Exercise 3: Scale the System (5 min)

```bash
# Scale application nodes
aws eks update-nodegroup-config \
  --cluster-name incidentfox-demo \
  --nodegroup-name incidentfox-demo-application \
  --scaling-config desiredSize=8 \
  --region us-west-2

# Scale a service
kubectl scale deployment frontend -n otel-demo --replicas=3

# Watch
kubectl get nodes
kubectl get pods -n otel-demo | grep frontend
```

---

# Part 9: Files Reference

## Must Understand

| File | Lines | Why Important |
|------|-------|---------------|
| `terraform/main.tf` | ~400 | Orchestrates all infrastructure |
| `terraform/modules/vpc/main.tf` | ~150 | Network foundation |
| `terraform/modules/eks/main.tf` | ~200 | Kubernetes cluster |
| `terraform/modules/irsa/main.tf` | ~80 | Security (IRSA) |
| `scripts/build-all.sh` | ~300 | Deployment automation |

## Nice to Know

| File | Purpose |
|------|---------|
| `terraform/modules/secrets/main.tf` | Secrets storage |
| `scripts/trigger-incident.sh` | Incident orchestration |
| `scripts/scenarios/*.sh` | Individual incidents |
| `helm/values-aws-simple.yaml` | Kubernetes config |

---

# Part 10: Next Steps

**Now you understand:**
- ✅ How infrastructure is defined (Terraform)
- ✅ How secrets are managed (AWS → IRSA → k8s)
- ✅ How deployment works (build-all.sh)
- ✅ How incidents are triggered (feature flags)
- ✅ How the system actually runs

**You can now:**
- Modify Terraform configs (change instance types, add resources)
- Add new secrets (extend secrets module)
- Create new incident scenarios (add flag + script)
- Connect your IncidentFox agent (you understand the endpoints)

**Questions to explore:**
- How does Helm work? (Read helm charts)
- How does OTel instrumentation work? (Read service code)
- How to add custom metrics? (Extend Prometheus)
- How to create Grafana dashboards? (Grafana UI)

---

**Ready to dive into any specific area? Or questions about what you've learned?**

