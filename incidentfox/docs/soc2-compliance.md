# SOC2 Compliance Configuration

## Overview

This document describes the SOC2 compliance controls implemented in the IncidentFox infrastructure.

## Compliance Requirements Met

### 1. Encryption at Rest ✅

**Requirement:** All data at rest must be encrypted using industry-standard encryption.

**Implementation:**

#### EBS Volumes (Kubernetes Persistent Storage)
- **Status:** ✅ Enabled
- **Method:** AWS KMS encryption with customer-managed key
- **Key Rotation:** Enabled (automatic annual rotation)
- **Scope:** All EBS volumes attached to EKS nodes and used by pods

**Configuration:**
```hcl
# KMS key with automatic rotation
resource "aws_kms_key" "ebs" {
  description             = "KMS key for EBS volume encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

# All EBS volumes encrypted with this key
encrypted = true
kms_key_id = aws_kms_key.ebs.arn
```

#### AWS Secrets Manager
- **Status:** ✅ Enabled by default
- **Method:** AWS-managed encryption
- **Scope:** All secrets (PostgreSQL credentials, Grafana credentials)

#### EKS Control Plane
- **Status:** ✅ Enabled by default
- **Method:** AWS-managed encryption
- **Scope:** All EKS control plane data (etcd)

### 2. Backups and Retention ✅

**Requirement:** Daily backups with minimum 7-day retention.

**Implementation:**

#### AWS Backup Plan
- **Status:** ✅ Enabled
- **Schedule:** Daily at 5:00 AM UTC
- **Retention:** 7 days
- **Backup Type:** Automated snapshots
- **Scope:** All EBS volumes tagged with `BackupRequired=true`

**Configuration:**
```hcl
resource "aws_backup_plan" "daily" {
  name = "${var.cluster_name}-daily-backup"
  
  rule {
    rule_name         = "daily-ebs-backup"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 5 * * ? *)"  # Daily at 5 AM UTC
    
    lifecycle {
      delete_after = 7  # 7-day retention
    }
  }
}
```

#### Backup Vault Encryption
- **Status:** ✅ Encrypted
- **Method:** Same KMS key as EBS volumes
- **Benefit:** Backups are encrypted both in transit and at rest

### 3. Audit Logging ✅

**Requirement:** Comprehensive audit logs for security and compliance monitoring.

**Implementation:**

#### EKS Control Plane Logs
- **Status:** ✅ Enabled
- **Types:** API, Audit, Authenticator, ControllerManager, Scheduler
- **Destination:** CloudWatch Logs
- **Retention:** 90 days (can be configured)

**Configuration:**
```hcl
resource "aws_eks_cluster" "main" {
  enabled_cluster_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]
}
```

## SOC2-Relevant Tags

All resources are tagged for compliance tracking:

```hcl
Compliance         = "SOC2"
DataClassification = "Confidential"
BackupRequired     = "true"
EncryptionRequired = "true"
```

## Verification

### Verify Encryption

```bash
# Check KMS key
aws kms describe-key --key-id $(terraform output -raw ebs_kms_key_id)

# Verify key rotation is enabled
aws kms get-key-rotation-status --key-id $(terraform output -raw ebs_kms_key_id)

# Check EBS volumes are encrypted
aws ec2 describe-volumes \
  --filters "Name=tag:kubernetes.io/cluster/incidentfox-demo,Values=owned" \
  --query 'Volumes[*].[VolumeId,Encrypted,KmsKeyId]' \
  --output table
```

### Verify Backups

```bash
# List backup plans
aws backup list-backup-plans

# Check backup vault
aws backup describe-backup-vault \
  --backup-vault-name $(terraform output -raw backup_vault_name)

# List recent backups
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name $(terraform output -raw backup_vault_name)

# Verify backup retention (should show 7 days)
aws backup get-backup-plan \
  --backup-plan-id $(terraform output -raw backup_plan_id)
```

### Verify Audit Logging

```bash
# Check EKS logging configuration
aws eks describe-cluster \
  --name $(terraform output -raw cluster_name) \
  --query 'cluster.logging.clusterLogging[0].types'

# View audit logs
aws logs tail /aws/eks/incidentfox-demo/cluster --follow
```

## Deployment

### Deploy SOC2-Compliant Infrastructure

```bash
cd incidentfox/terraform

# Initialize (if not already done)
terraform init

# Review changes
terraform plan

# Apply SOC2 configurations
terraform apply
```

**Expected Changes:**
- ✅ Creates KMS key with rotation
- ✅ Creates backup vault
- ✅ Creates daily backup plan
- ✅ Updates node groups with encrypted launch templates
- ✅ Enables EBS encryption on all volumes

### Zero Downtime Deployment

The changes will be applied with minimal disruption:

1. **KMS Key & Backup:** No impact (new resources)
2. **Node Groups:** Rolling update
   - New encrypted nodes are launched
   - Pods are drained from old nodes
   - Old nodes are terminated
   - **Duration:** ~10-15 minutes

**To monitor deployment:**
```bash
# Watch node rollout
kubectl get nodes -w

# Check pod status
kubectl get pods -A -w
```

## Cost Impact

**Additional Monthly Costs:**

| Resource | Cost | Notes |
|----------|------|-------|
| KMS Key | $1/month | Per key |
| KMS Key Usage | ~$0.03/month | API calls (minimal) |
| AWS Backup Storage | ~$0.50/GB/month | 7-day retention of ~10GB = $5/month |
| Backup API Calls | ~$1/month | Snapshots, restores |
| **Total** | **~$7/month** | <3% of total infra cost |

## SOC2 Audit Evidence

### Documents for Auditors:

1. **Encryption Policy:** This document (soc2-compliance.md)
2. **Terraform Configuration:** `terraform/main.tf` (IaC proof)
3. **KMS Key Details:** `terraform output soc2_compliance_summary`
4. **Backup Evidence:**
   ```bash
   aws backup list-recovery-points-by-backup-vault \
     --backup-vault-name incidentfox-demo-backup-vault \
     --output json > backup-evidence.json
   ```
5. **Audit Logs:** CloudWatch Logs exports

### Compliance Controls Mapping:

| SOC2 Control | Implementation | Verification Method |
|--------------|----------------|---------------------|
| CC6.1 (Logical Access) | AWS IAM, IRSA | IAM policy review |
| CC6.6 (Encryption) | KMS, encrypted EBS | `aws ec2 describe-volumes` |
| CC6.7 (Data Retention) | 7-day backup retention | `aws backup get-backup-plan` |
| CC7.2 (System Monitoring) | CloudWatch, EKS logging | Log exports |
| CC8.1 (Change Management) | Terraform IaC, Git history | Terraform state, Git log |

## Maintenance

### Regular Tasks:

**Monthly:**
- [ ] Verify backups are completing: `aws backup list-backup-jobs --by-state COMPLETED`
- [ ] Check backup storage usage: `aws backup describe-backup-vault`
- [ ] Review KMS key access logs (CloudTrail)

**Quarterly:**
- [ ] Test restore procedure
- [ ] Review and update retention policy if needed
- [ ] Audit KMS key permissions

**Annually:**
- [ ] SOC2 audit preparation
- [ ] Review encryption standards
- [ ] Verify key rotation occurred

## Disaster Recovery

### Restore from Backup:

```bash
# 1. List available recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name incidentfox-demo-backup-vault

# 2. Restore a volume
aws backup start-restore-job \
  --recovery-point-arn <arn-from-step-1> \
  --metadata-file restore-metadata.json \
  --iam-role-arn <backup-role-arn>

# 3. Attach restored volume to instance
aws ec2 attach-volume \
  --volume-id <restored-volume-id> \
  --instance-id <instance-id> \
  --device /dev/sdf
```

### RTO/RPO:

- **Recovery Point Objective (RPO):** 24 hours (daily backups)
- **Recovery Time Objective (RTO):** <2 hours (automated restore)

## Additional Security Features

### Already Enabled:

✅ **IMDSv2 Required** - Prevents SSRF attacks on metadata service
✅ **Private Subnets** - EKS nodes not directly accessible from internet
✅ **NAT Gateway** - Controlled egress
✅ **Security Groups** - Network isolation
✅ **IRSA** - No long-lived credentials in pods
✅ **Secrets Manager** - Centralized, encrypted secret storage

## Compliance Checklist

- [x] Encryption at rest enabled (EBS, Secrets Manager)
- [x] KMS key rotation enabled
- [x] Daily backups configured
- [x] 7-day retention policy set
- [x] Backup vault encrypted
- [x] Audit logging enabled (EKS control plane)
- [x] All resources tagged for compliance
- [x] IAM roles follow least privilege
- [x] Network isolation (private subnets)
- [x] Automated backup selection (tag-based)

## References

- [AWS SOC2 Compliance](https://aws.amazon.com/compliance/soc-2/)
- [EKS Security Best Practices](https://aws.github.io/aws-eks-best-practices/security/docs/)
- [AWS Backup Documentation](https://docs.aws.amazon.com/aws-backup/)
- [KMS Best Practices](https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html)
