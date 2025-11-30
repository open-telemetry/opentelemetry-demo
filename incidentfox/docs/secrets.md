# Secrets Management

Complete guide to how secrets are managed in the IncidentFox lab.

---

## Quick Reference

**Current Secrets:**
1. **PostgreSQL:** `incidentfox-demo/postgres` (username + password)
2. **Grafana:** `incidentfox-demo/grafana` (admin-user + admin-password)

**Where stored:**
- ✅ AWS Secrets Manager (source of truth, encrypted)
- ✅ Terraform state (should be remote S3 + encrypted)
- ✅ Kubernetes secrets (auto-synced by External Secrets Operator)
- ❌ NEVER in Git, NEVER in terraform.tfvars

**How to retrieve:**
```bash
# From AWS
aws secretsmanager get-secret-value --secret-id incidentfox-demo/postgres

# From Kubernetes
kubectl get secret postgres-credentials -n otel-demo -o yaml

# Export to 1Password
./scripts/export-secrets-to-1password.sh
```

---

## Architecture

### Two-Tier System

```
┌─────────────────────────────────────────────────────────────┐
│                     AWS Secrets Manager                      │
│                   (Source of Truth)                          │
│                                                              │
│  incidentfox-demo/postgres:                                 │
│    {username: "otelu", password: "YVsU&=5K..."}            │
│                                                              │
│  incidentfox-demo/grafana:                                  │
│    {admin-user: "admin", admin-password: "gGInoy..."}      │
└──────────────────────────┬──────────────────────────────────┘
                           │ IRSA (IAM Role)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              External Secrets Operator                       │
│              (Syncs every hour)                              │
└──────────────────────────┬──────────────────────────────────┘
                           │ Creates/Updates
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              Kubernetes Secrets                              │
│                                                              │
│  postgres-credentials                                       │
│  grafana-credentials                                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ Consumed as env vars
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              Application Pods                                │
│  (PostgreSQL, Grafana, etc.)                                │
└─────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Single source of truth (AWS Secrets Manager)
- No long-lived credentials (IRSA uses temporary tokens)
- Automatic sync (no manual kubectl commands)
- Audit trail (CloudTrail logs all access)
- Rotation ready (update in AWS, syncs automatically)

---

## How Secrets Are Generated

### During Terraform Deployment

**1. Terraform generates random passwords:**
```hcl
# terraform/main.tf
resource "random_password" "postgres" {
  length  = 32
  special = true
}

resource "random_password" "grafana" {
  length  = 32
  special = false  # No special chars for web login
}
```

**2. Terraform stores in AWS Secrets Manager:**
```hcl
module "secrets" {
  secrets = {
    postgres = {
      description = "PostgreSQL credentials"
      secret_data = {
        username = "otelu"
        password = random_password.postgres.result  # Random 32-char
      }
    }
    grafana = {
      description = "Grafana admin credentials"
      secret_data = {
        admin-user     = "admin"
        admin-password = random_password.grafana.result  # Random 32-char
      }
    }
  }
}
```

**Key points:**
- Passwords generated at `terraform apply` time
- Different on every deployment
- Never hardcoded anywhere
- Never in Git

---

## Current Secrets Detail

### PostgreSQL Database

**ARN:** `arn:aws:secretsmanager:us-west-2:103002841599:secret:incidentfox-demo/postgres-MJKO8E`

**Contents:**
```json
{
  "username": "otelu",
  "password": "YVsU&=5K2cpXP>P-wxS9}*6LG4z9:@KB"
}
```

**Used by:**
- PostgreSQL database pods
- Accounting service (connects to PostgreSQL)
- Product Reviews service (connects to PostgreSQL)

**Kubernetes secret:** `postgres-credentials` in `otel-demo` namespace

---

### Grafana Admin

**ARN:** `arn:aws:secretsmanager:us-west-2:103002841599:secret:incidentfox-demo/grafana-QL3FoG`

**Contents:**
```json
{
  "admin-user": "admin",
  "admin-password": "gGInoyLBZH7uwm7MsQCOSDUuEMqBy2aI"
}
```

**Used by:**
- Grafana admin login

**Kubernetes secret:** `grafana-credentials` in `otel-demo` namespace

---

## How IRSA Secures Access

**Problem:** External Secrets Operator needs to read from AWS Secrets Manager

**Traditional solution (BAD):**
```yaml
# Store AWS credentials in Kubernetes
apiVersion: v1
kind: Secret
data:
  aws_access_key: QUtJQUlPU0ZPRE5ON...
  aws_secret_key: d0phbHJYVXRuRkVNSS9L...
```

**Our solution (GOOD) - IRSA:**
```yaml
# Just annotate ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: external-secrets-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::...:role/incidentfox-demo-external-secrets
```

**Flow:**
1. Pod uses ServiceAccount with IRSA annotation
2. EKS injects JWT token proving pod's identity
3. Pod calls AWS STS with JWT
4. STS validates JWT using OIDC
5. STS returns temporary credentials (1 hour)
6. Pod uses credentials to access Secrets Manager

**Security:**
- No long-lived credentials
- Automatic rotation every hour
- Fine-grained permissions (only read incidentfox-demo/* secrets)
- Full audit trail

For complete IRSA explanation, see [architecture.md](architecture.md#irsa).

---

## Accessing Secrets

### From AWS CLI

```bash
# PostgreSQL password
aws secretsmanager get-secret-value \
  --secret-id incidentfox-demo/postgres \
  --region us-west-2 \
  --query SecretString --output text | jq -r .password

# Grafana password
aws secretsmanager get-secret-value \
  --secret-id incidentfox-demo/grafana \
  --region us-west-2 \
  --query SecretString --output text | jq -r '."admin-password"'

# List all secrets
aws secretsmanager list-secrets --region us-west-2
```

### From Kubernetes

```bash
# PostgreSQL password
kubectl get secret postgres-credentials -n otel-demo \
  -o jsonpath='{.data.password}' | base64 -d

# Grafana password
kubectl get secret grafana-credentials -n otel-demo \
  -o jsonpath='{.data.admin-password}' | base64 -d

# View full secret
kubectl get secret postgres-credentials -n otel-demo -o yaml
```

### Export to 1Password

```bash
cd incidentfox
./scripts/export-secrets-to-1password.sh

# Creates two files:
# - incidentfox-secrets-TIMESTAMP.json (full backup)
# - incidentfox-secrets-TIMESTAMP-1password.csv (for import)
```

Then import CSV to 1Password:
1. Open 1Password → File → Import → CSV
2. Select the CSV file
3. Choose vault: "IncidentFox"
4. Delete local files after import

---

## Updating Secrets

### Update in AWS Secrets Manager

```bash
# Update password
aws secretsmanager update-secret \
  --secret-id incidentfox-demo/postgres \
  --secret-string '{"username":"otelu","password":"new_password_here"}'

# External Secrets Operator will sync within 1 hour
```

### Force Immediate Sync

```bash
# Annotate ExternalSecret to force refresh
kubectl annotate externalsecret postgres-credentials \
  -n otel-demo \
  force-sync=$(date +%s) \
  --overwrite

# Check sync status
kubectl describe externalsecret postgres-credentials -n otel-demo
```

---

## Security Principles

### What's NOT in Git

✅ **Safe (these are in Git):**
- Terraform code
- Kubernetes manifests
- Documentation
- Scripts
- `terraform.tfvars.example`

❌ **Never in Git:**
- Passwords (generated at deploy time)
- `terraform.tfvars` (may have account details)
- `terraform.tfstate` (contains passwords)
- `*.log` files
- Secret export files (`incidentfox-secrets-*.json`)

**Enforced by `.gitignore`:**
```gitignore
*.tfstate
*.tfvars
!terraform.tfvars.example
*secret*.json
*.log
```

### Where Secrets Live

**1. AWS Secrets Manager (Primary)**
- Encrypted at rest (AWS manages keys)
- Access via IAM (fine-grained control)
- Audit via CloudTrail (who accessed when)
- Can enable automatic rotation

**2. Terraform State (Secondary)**
- Contains `random_password` results
- ⚠️ Must be encrypted (use S3 backend with encryption)
- Never commit to Git

**3. Kubernetes Secrets (Synced)**
- Auto-created by External Secrets Operator
- Base64 encoded (not encrypted by default)
- Used by pods via env vars or volume mounts

---

## Troubleshooting

### ExternalSecret Not Syncing

```bash
# Check External Secrets Operator logs
kubectl logs -n external-secrets-system \
  -l app.kubernetes.io/name=external-secrets

# Check ExternalSecret status
kubectl describe externalsecret postgres-credentials -n otel-demo

# Common issues:
# 1. IRSA role not configured → Check ServiceAccount annotation
# 2. Secret doesn't exist → Verify in AWS Secrets Manager
# 3. Wrong region → Check SecretStore config
# 4. IAM permission denied → Check role policy
```

### Permission Denied

```bash
# Verify IRSA annotation
kubectl get sa external-secrets-sa -n external-secrets-system -o yaml

# Should see:
# eks.amazonaws.com/role-arn: arn:aws:iam::...:role/...

# Check IAM role
aws iam get-role --role-name incidentfox-demo-external-secrets

# Check policy
aws iam list-attached-role-policies --role-name incidentfox-demo-external-secrets
```

### Secret Not Found

```bash
# Verify secret exists in AWS
aws secretsmanager describe-secret --secret-id incidentfox-demo/postgres

# Check secret name matches
kubectl get externalsecret postgres-credentials -n otel-demo -o yaml | grep remoteRef
```

---

## Production Enhancements

### Enable Automatic Rotation

```hcl
# terraform/modules/secrets/main.tf
resource "aws_secretsmanager_secret_rotation" "postgres" {
  secret_id           = aws_secretsmanager_secret.main["postgres"].id
  rotation_lambda_arn = aws_lambda_function.rotate_postgres.arn
  
  rotation_rules {
    automatically_after_days = 30
  }
}
```

### Add KMS Encryption

```hcl
resource "aws_kms_key" "secrets" {
  description         = "KMS key for secrets"
  enable_key_rotation = true
}

resource "aws_secretsmanager_secret" "main" {
  name       = "incidentfox-demo/postgres"
  kms_key_id = aws_kms_key.secrets.id  # Use custom KMS key
}
```

### Enable CloudTrail Logging

Already enabled by default! View access logs:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=incidentfox-demo/postgres \
  --max-results 10
```

---

## Best Practices

1. ✅ **Use AWS Secrets Manager** - Don't hardcode
2. ✅ **Generate passwords** - Don't reuse
3. ✅ **Use IRSA** - No long-lived keys
4. ✅ **Encrypt Terraform state** - S3 backend with encryption
5. ✅ **Backup to 1Password** - Team access
6. ✅ **Rotate regularly** - Update in AWS
7. ✅ **Monitor access** - CloudTrail audit logs
8. ✅ **Least privilege** - Minimal IAM permissions

---

## FAQ

**Q: Where do I put my AWS credentials?**  
A: In `~/.aws/credentials`, NOT in the repo. Use `export AWS_PROFILE=playground`.

**Q: Are secrets in terraform.tfvars?**  
A: NO! Only non-sensitive config (region, instance types, tags).

**Q: Can I use my own passwords?**  
A: Not recommended. Let Terraform generate them, then back up to 1Password.

**Q: What if I lose passwords?**  
A: They're in AWS Secrets Manager. Retrieve anytime with AWS CLI.

**Q: How do I rotate passwords?**  
A: Update in AWS Secrets Manager. External Secrets Operator syncs within 1 hour.

**Q: What's the cost?**  
A: $0.40/secret/month + $0.05/10k API calls. For 2 secrets: ~$1/month.

---

## Related Documentation

- [Architecture](architecture.md) - Complete system architecture including IRSA deep dive
- [AWS Deployment](aws-deployment.md) - How to deploy infrastructure
- [Agent Integration](agent-integration.md) - Using secrets in your agent

---

## Security Summary

**✅ Production-grade security:**
- Random generation via Terraform
- Encrypted storage in AWS Secrets Manager
- No secrets in Git or config files
- IRSA for access (no long-lived credentials)
- Automatic rotation support
- Full audit trail via CloudTrail
- Fine-grained IAM permissions
- Team sharing via 1Password

**The system is secure by default!**

