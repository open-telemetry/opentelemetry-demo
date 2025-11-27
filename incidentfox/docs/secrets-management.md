# Secrets Management - Production Grade Approach

This document explains how secrets are managed in the IncidentFox lab environment using AWS best practices.

## Overview

We use a **two-tier architecture** for secrets management:

1. **AWS Secrets Manager** - Centralized secret storage in AWS
2. **External Secrets Operator** - Kubernetes operator that syncs secrets from AWS to k8s

This approach provides:
- ✅ Centralized secret management
- ✅ Automatic rotation capabilities
- ✅ Audit logging (CloudTrail)
- ✅ Fine-grained access control (IAM)
- ✅ No secrets in Git or Terraform state
- ✅ Kubernetes-native secret consumption

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          AWS                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            AWS Secrets Manager                         │ │
│  │                                                          │ │
│  │  • incidentfox-demo/postgres                           │ │
│  │      {username: "otelu", password: "..."}              │ │
│  │                                                          │ │
│  │  • incidentfox-demo/grafana                            │ │
│  │      {admin-user: "admin", admin-password: "..."}      │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│                    (IRSA with IAM Role)                      │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              EKS Cluster                                │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────┐          │ │
│  │  │   External Secrets Operator              │          │ │
│  │  │                                            │          │ │
│  │  │   • SecretStore (AWS Secrets Manager)    │          │ │
│  │  │   • ExternalSecret (postgres)            │          │ │
│  │  │   • ExternalSecret (grafana)             │          │ │
│  │  └──────────────────────────────────────────┘          │ │
│  │                   ↓   ↓   ↓                              │ │
│  │  ┌──────────────────────────────────────────┐          │ │
│  │  │   Kubernetes Secrets (auto-synced)       │          │ │
│  │  │                                            │          │ │
│  │  │   • postgres-credentials                 │          │ │
│  │  │   • grafana-credentials                  │          │ │
│  │  └──────────────────────────────────────────┘          │ │
│  │                       ↓                                  │ │
│  │  ┌──────────────────────────────────────────┐          │ │
│  │  │   Application Pods                       │          │ │
│  │  │                                            │          │ │
│  │  │   • PostgreSQL (reads secret)            │          │ │
│  │  │   • Grafana (reads secret)               │          │ │
│  │  │   • Other services...                    │          │ │
│  │  └──────────────────────────────────────────┘          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Secrets Created in AWS Secrets Manager

Terraform creates secrets in AWS Secrets Manager:

```hcl
# terraform/modules/secrets/main.tf
resource "aws_secretsmanager_secret" "main" {
  name        = "incidentfox-demo/postgres"
  description = "PostgreSQL credentials for OTel Demo"
}

resource "aws_secretsmanager_secret_version" "main" {
  secret_id     = aws_secretsmanager_secret.main.id
  secret_string = jsonencode({
    username = "otelu"
    password = random_password.postgres.result
  })
}
```

**Generated passwords** are created by Terraform using `random_password` resource, ensuring:
- Unique per environment
- Secure (32 characters)
- Never stored in Git
- Stored only in Terraform state (encrypted) and AWS Secrets Manager

### 2. IAM Role with IRSA

The External Secrets Operator needs permission to read from Secrets Manager. We use **IRSA** (IAM Roles for Service Accounts):

```hcl
# terraform/modules/irsa/main.tf
module "external_secrets_irsa" {
  source = "./modules/irsa"
  
  namespace            = "external-secrets-system"
  service_account_name = "external-secrets-sa"
  
  policy_statements = [
    {
      effect = "Allow"
      actions = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
      ]
      resources = [
        "arn:aws:secretsmanager:us-west-2:*:secret:incidentfox-demo/*"
      ]
    }
  ]
}
```

**IRSA** allows Kubernetes service accounts to assume AWS IAM roles without:
- Long-lived credentials
- Access keys stored anywhere
- Secrets in environment variables

### 3. External Secrets Operator Deployed

The `build-all.sh` script deploys External Secrets Operator via Helm:

```bash
helm upgrade --install external-secrets \
  external-secrets/external-secrets \
  --namespace external-secrets-system \
  --create-namespace
```

### 4. SecretStore Configured

A `SecretStore` tells the operator where to find secrets:

```yaml
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
            name: external-secrets-sa  # Uses IRSA
```

### 5. ExternalSecret Resources Created

`ExternalSecret` resources define which secrets to sync:

```yaml
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
    creationPolicy: Owner
  data:
    - secretKey: password
      remoteRef:
        key: incidentfox-demo/postgres
        property: password
    - secretKey: username
      remoteRef:
        key: incidentfox-demo/postgres
        property: username
```

The operator:
1. Reads from AWS Secrets Manager using IRSA
2. Creates/updates a Kubernetes Secret named `postgres-credentials`
3. Refreshes every hour automatically

### 6. Applications Consume Secrets

Applications use standard Kubernetes secret references:

```yaml
# PostgreSQL deployment
env:
  - name: POSTGRES_USER
    valueFrom:
      secretKeyRef:
        name: postgres-credentials
        key: username
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgres-credentials
        key: password
```

## Security Benefits

### 1. **No Secrets in Git**
- Never commit secrets to version control
- Terraform uses `random_password` and AWS Secrets Manager
- All sensitive data stays in AWS

### 2. **Centralized Management**
- Single source of truth (AWS Secrets Manager)
- Easy rotation without Kubernetes restarts
- Consistent across environments

### 3. **Fine-Grained Access Control**
- IAM policies control who/what can read secrets
- Kubernetes RBAC controls pod access
- Audit via CloudTrail

### 4. **Automatic Rotation**
- External Secrets Operator refreshes secrets hourly
- Can configure AWS Secrets Manager rotation
- Zero-downtime rotation possible

### 5. **No Long-Lived Credentials**
- IRSA uses temporary credentials
- No AWS access keys in cluster
- Credentials refresh automatically

## Production Enhancements

### 1. Enable Secret Rotation

```hcl
resource "aws_secretsmanager_secret_rotation" "postgres" {
  secret_id           = aws_secretsmanager_secret.postgres.id
  rotation_lambda_arn = aws_lambda_function.rotate_postgres.arn
  
  rotation_rules {
    automatically_after_days = 30
  }
}
```

### 2. Use KMS Encryption

```hcl
resource "aws_kms_key" "secrets" {
  description = "KMS key for secrets"
  enable_key_rotation = true
}

resource "aws_secretsmanager_secret" "main" {
  name       = "incidentfox-demo/postgres"
  kms_key_id = aws_kms_key.secrets.id
}
```

### 3. Enable CloudTrail Logging

```hcl
resource "aws_cloudtrail" "secrets" {
  name                          = "secrets-audit"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  
  event_selector {
    read_write_type           = "All"
    include_management_events = true
  }
}
```

### 4. Implement Secret Scanning

Add to CI/CD:
```yaml
- name: Scan for secrets
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: main
```

## Accessing Secrets

### Via AWS CLI

```bash
# List secrets
aws secretsmanager list-secrets

# Get secret value
aws secretsmanager get-secret-value \
  --secret-id incidentfox-demo/postgres \
  --query SecretString \
  --output text | jq .

# Update secret (triggers sync to k8s within 1 hour)
aws secretsmanager update-secret \
  --secret-id incidentfox-demo/postgres \
  --secret-string '{"username":"otelu","password":"newpass"}'
```

### Via Kubectl

```bash
# List ExternalSecrets
kubectl get externalsecret -n otel-demo

# Check sync status
kubectl describe externalsecret postgres-credentials -n otel-demo

# View synced Kubernetes secret
kubectl get secret postgres-credentials -n otel-demo -o yaml

# Decode secret value
kubectl get secret postgres-credentials -n otel-demo \
  -o jsonpath='{.data.password}' | base64 -d
```

### Via Terraform Output

```bash
# Get secret ARNs
terraform output secrets

# Note: Values are marked sensitive and won't be shown
```

## Troubleshooting

### ExternalSecret Not Syncing

```bash
# Check External Secrets Operator logs
kubectl logs -n external-secrets-system \
  -l app.kubernetes.io/name=external-secrets

# Check ExternalSecret status
kubectl describe externalsecret postgres-credentials -n otel-demo

# Common issues:
# 1. IRSA role not configured correctly
# 2. Secret doesn't exist in AWS Secrets Manager
# 3. Wrong region configured
# 4. IAM permissions insufficient
```

### Permission Denied Errors

```bash
# Verify IRSA role is attached to service account
kubectl get sa external-secrets-sa -n external-secrets-system -o yaml

# Should see annotation:
# eks.amazonaws.com/role-arn: arn:aws:iam::...:role/...

# Test IAM permissions
aws sts assume-role-with-web-identity \
  --role-arn <role-arn> \
  --role-session-name test \
  --web-identity-token <token>
```

### Secret Not Found

```bash
# Verify secret exists
aws secretsmanager describe-secret \
  --secret-id incidentfox-demo/postgres

# Check secret name matches ExternalSecret spec
kubectl get externalsecret postgres-credentials -n otel-demo -o yaml
```

## Cost Optimization

AWS Secrets Manager pricing:
- **$0.40 per secret per month**
- **$0.05 per 10,000 API calls**

For the demo with 2 secrets:
- Monthly cost: ~$0.80
- API calls: Negligible (refreshes every hour)
- **Total: < $1/month**

## Migration Guide

### From Kubernetes Secrets

```bash
# 1. Export existing secret
kubectl get secret my-secret -n otel-demo -o json > secret.json

# 2. Extract values
cat secret.json | jq -r '.data.password' | base64 -d

# 3. Create in AWS Secrets Manager
aws secretsmanager create-secret \
  --name incidentfox-demo/my-secret \
  --secret-string '{"password":"..."}'

# 4. Create ExternalSecret
kubectl apply -f externalsecret.yaml

# 5. Delete old secret
kubectl delete secret my-secret -n otel-demo
```

### From Environment Variables

```bash
# Never do this in production!
# BAD: environment = { DB_PASSWORD = "hardcoded" }

# GOOD: Use AWS Secrets Manager + ExternalSecret
```

## Best Practices

1. **Never commit secrets** - Use AWS Secrets Manager
2. **Use IRSA** - No access keys in cluster
3. **Enable rotation** - Rotate secrets regularly
4. **Audit access** - Enable CloudTrail
5. **Encrypt at rest** - Use KMS for additional security
6. **Least privilege** - IAM policies should be specific
7. **Separate per environment** - Different secrets for dev/staging/prod
8. **Monitor sync status** - Alert on ExternalSecret failures

## References

- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [External Secrets Operator](https://external-secrets.io/)
- [EKS IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)

