# IncidentFox: Main Terraform configuration
# 
# This deploys:
# - VPC with public/private subnets across 2 AZs
# - EKS cluster with managed node groups
# - AWS Secrets Manager for sensitive data
# - IAM roles for External Secrets Operator (IRSA)

# Version constraints are in versions.tf

# Provider configuration
provider "aws" {
  region = var.region

  default_tags {
    tags = merge(
      var.tags,
      {
        Environment = var.environment
        Project     = "incidentfox"
        ManagedBy   = "terraform"
      }
    )
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# ===================================================================
# SOC2 Compliance: KMS Key for Encryption at Rest
# ===================================================================

resource "aws_kms_key" "ebs" {
  description             = "KMS key for EBS volume encryption (SOC2 compliance)"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  
  # KMS key policy allowing EKS/EC2 to use it
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow EKS to use the key"
        Effect = "Allow"
        Principal = {
          Service = [
            "ec2.amazonaws.com",
            "eks.amazonaws.com"
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ec2.${var.region}.amazonaws.com"
          }
        }
      },
      {
        Sid    = "Allow EC2 AutoScaling to use the key"
        Effect = "Allow"
        Principal = {
          Service = "autoscaling.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name       = "${var.cluster_name}-ebs-key"
      Purpose    = "EBS Encryption"
      Compliance = "SOC2"
    }
  )
}

resource "aws_kms_alias" "ebs" {
  name          = "alias/${var.cluster_name}-ebs"
  target_key_id = aws_kms_key.ebs.key_id
}

# ===================================================================
# SOC2 Compliance: AWS Backup Plan
# ===================================================================

resource "aws_backup_vault" "main" {
  name        = "${var.cluster_name}-backup-vault"
  kms_key_arn = aws_kms_key.ebs.arn

  tags = merge(
    var.tags,
    {
      Name       = "${var.cluster_name}-backup-vault"
      Compliance = "SOC2"
    }
  )
}

resource "aws_backup_plan" "daily" {
  name = "${var.cluster_name}-daily-backup"

  rule {
    rule_name         = "daily-ebs-backup"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 5 * * ? *)" # Daily at 5 AM UTC

    lifecycle {
      delete_after = 7 # 7-day retention per SOC2 requirement
    }

    recovery_point_tags = merge(
      var.tags,
      {
        BackupType = "Automated"
        Compliance = "SOC2"
      }
    )
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.cluster_name}-backup-plan"
      Compliance = "SOC2"
    }
  )
}

# IAM Role for AWS Backup
resource "aws_iam_role" "backup" {
  name = "${var.cluster_name}-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "backup.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-backup-role"
    }
  )
}

resource "aws_iam_role_policy_attachment" "backup" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
  role       = aws_iam_role.backup.name
}

resource "aws_iam_role_policy_attachment" "backup_restore" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
  role       = aws_iam_role.backup.name
}

# Backup Selection: All EBS volumes with backup tag
resource "aws_backup_selection" "ebs_volumes" {
  name         = "${var.cluster_name}-ebs-volumes"
  plan_id      = aws_backup_plan.daily.id
  iam_role_arn = aws_iam_role.backup.arn

  selection_tag {
    type  = "STRINGEQUALS"
    key   = "BackupRequired"
    value = "true"
  }

  selection_tag {
    type  = "STRINGEQUALS"
    key   = "kubernetes.io/cluster/${local.cluster_name}"
    value = "owned"
  }
}

# Local variables
locals {
  cluster_name = var.cluster_name
  azs          = slice(data.aws_availability_zones.available.names, 0, 2)

  # Secrets prefix
  secrets_prefix = var.cluster_name

  # SOC2 Compliance tags
  compliance_tags = {
    Compliance         = "SOC2"
    DataClassification = "Confidential"
    BackupRequired     = "true"
    EncryptionRequired = "true"
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  # Public subnets for ALB
  public_subnets = [
    cidrsubnet(var.vpc_cidr, 4, 0), # e.g., 10.0.0.0/20
    cidrsubnet(var.vpc_cidr, 4, 1), # e.g., 10.0.16.0/20
  ]

  # Private subnets for EKS nodes
  private_subnets = [
    cidrsubnet(var.vpc_cidr, 4, 2), # e.g., 10.0.32.0/20
    cidrsubnet(var.vpc_cidr, 4, 3), # e.g., 10.0.48.0/20
  ]

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment == "dev" ? true : false # Cost optimization for dev
  enable_dns_hostnames = true
  enable_dns_support   = true

  # EKS-specific tags
  public_subnet_tags = {
    "kubernetes.io/role/elb"                      = "1"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"             = "1"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  tags = var.tags
}

# EKS Module
module "eks" {
  source = "./modules/eks"

  cluster_name    = local.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # SOC2 Compliance: Enable encryption for all EBS volumes
  enable_ebs_encryption = true
  ebs_kms_key_id        = aws_kms_key.ebs.arn

  # Node groups
  node_groups = {
    # System node group for control plane components
    system = {
      desired_size   = var.system_node_desired_size
      min_size       = var.system_node_min_size
      max_size       = var.system_node_max_size
      instance_types = [var.system_node_instance_type]
      capacity_type  = "ON_DEMAND"

      labels = {
        role = "system"
      }

      taints = []
    }

    # Application node group for demo services
    application = {
      desired_size   = var.app_node_desired_size
      min_size       = var.app_node_min_size
      max_size       = var.app_node_max_size
      instance_types = [var.app_node_instance_type]
      capacity_type  = var.app_node_capacity_type # ON_DEMAND or SPOT

      labels = {
        role = "application"
      }

      taints = []
    }
  }

  # Enable IRSA (IAM Roles for Service Accounts)
  enable_irsa = true

  # Cluster add-ons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }

  tags = var.tags
}

# Secrets Management
module "secrets" {
  source = "./modules/secrets"

  cluster_name   = local.cluster_name
  secrets_prefix = local.secrets_prefix

  # Secrets to create in AWS Secrets Manager
  secrets = {
    postgres = {
      description = "PostgreSQL credentials for OTel Demo"
      secret_data = {
        username = "otelu"
        password = random_password.postgres.result
      }
    }
    grafana = {
      description = "Grafana admin credentials"
      secret_data = {
        admin-user     = "admin"
        admin-password = random_password.grafana.result
      }
    }
  }

  tags = var.tags
}

# Random passwords for services
resource "random_password" "postgres" {
  length  = 32
  special = true
}

resource "random_password" "grafana" {
  length  = 32
  special = false # Avoid special chars for web UI
}

# IAM Role for External Secrets Operator (IRSA)
module "external_secrets_irsa" {
  source = "./modules/irsa"

  cluster_name         = local.cluster_name
  oidc_provider_arn    = module.eks.oidc_provider_arn
  namespace            = "external-secrets-system"
  service_account_name = "external-secrets-sa"
  role_name            = "${local.cluster_name}-external-secrets"

  # Policy to read secrets from Secrets Manager
  policy_statements = [
    {
      effect = "Allow"
      actions = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
      ]
      resources = [
        "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${local.secrets_prefix}/*"
      ]
    }
  ]

  tags = var.tags
}

# IAM Role for AWS Load Balancer Controller (IRSA)
module "alb_controller_irsa" {
  source = "./modules/irsa"

  cluster_name         = local.cluster_name
  oidc_provider_arn    = module.eks.oidc_provider_arn
  namespace            = "kube-system"
  service_account_name = "aws-load-balancer-controller"
  role_name            = "${local.cluster_name}-alb-controller"

  # Load Balancer Controller policy
  policy_statements = [
    {
      effect = "Allow"
      actions = [
        "iam:CreateServiceLinkedRole"
      ]
      resources = ["*"]
      conditions = [
        {
          test     = "StringEquals"
          variable = "iam:AWSServiceName"
          values   = ["elasticloadbalancing.amazonaws.com"]
        }
      ]
    },
    {
      effect = "Allow"
      actions = [
        "ec2:DescribeAccountAttributes",
        "ec2:DescribeAddresses",
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeInternetGateways",
        "ec2:DescribeVpcs",
        "ec2:DescribeVpcPeeringConnections",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeInstances",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DescribeTags",
        "ec2:GetCoipPoolUsage",
        "ec2:DescribeCoipPools",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeLoadBalancerAttributes",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeListenerCertificates",
        "elasticloadbalancing:DescribeSSLPolicies",
        "elasticloadbalancing:DescribeRules",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetGroupAttributes",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:DescribeTags",
      ]
      resources = ["*"]
    },
    {
      effect = "Allow"
      actions = [
        "cognito-idp:DescribeUserPoolClient",
        "acm:ListCertificates",
        "acm:DescribeCertificate",
        "iam:ListServerCertificates",
        "iam:GetServerCertificate",
        "waf-regional:GetWebACL",
        "waf-regional:GetWebACLForResource",
        "waf-regional:AssociateWebACL",
        "waf-regional:DisassociateWebACL",
        "wafv2:GetWebACL",
        "wafv2:GetWebACLForResource",
        "wafv2:AssociateWebACL",
        "wafv2:DisassociateWebACL",
        "shield:GetSubscriptionState",
        "shield:DescribeProtection",
        "shield:CreateProtection",
        "shield:DeleteProtection",
      ]
      resources = ["*"]
    },
    {
      effect = "Allow"
      actions = [
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:CreateSecurityGroup",
      ]
      resources = ["*"]
    },
    {
      effect = "Allow"
      actions = [
        "ec2:CreateTags"
      ]
      resources = ["arn:aws:ec2:*:*:security-group/*"]
      conditions = [
        {
          test     = "StringEquals"
          variable = "ec2:CreateAction"
          values   = ["CreateSecurityGroup"]
        },
        {
          test     = "Null"
          variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
          values   = ["false"]
        }
      ]
    },
    {
      effect = "Allow"
      actions = [
        "ec2:CreateTags",
        "ec2:DeleteTags",
      ]
      resources = ["arn:aws:ec2:*:*:security-group/*"]
      conditions = [
        {
          test     = "Null"
          variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
          values   = ["true"]
        },
        {
          test     = "Null"
          variable = "aws:ResourceTag/elbv2.k8s.aws/cluster"
          values   = ["false"]
        }
      ]
    },
    {
      effect = "Allow"
      actions = [
        "ec2:DeleteSecurityGroup"
      ]
      resources = ["*"]
      conditions = [
        {
          test     = "Null"
          variable = "aws:ResourceTag/elbv2.k8s.aws/cluster"
          values   = ["false"]
        }
      ]
    },
    {
      effect = "Allow"
      actions = [
        "elasticloadbalancing:CreateLoadBalancer",
        "elasticloadbalancing:CreateTargetGroup",
      ]
      resources = ["*"]
      conditions = [
        {
          test     = "Null"
          variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
          values   = ["false"]
        }
      ]
    },
    {
      effect = "Allow"
      actions = [
        "elasticloadbalancing:CreateListener",
        "elasticloadbalancing:DeleteListener",
        "elasticloadbalancing:CreateRule",
        "elasticloadbalancing:DeleteRule",
      ]
      resources = ["*"]
    },
    {
      effect = "Allow"
      actions = [
        "elasticloadbalancing:AddTags",
        "elasticloadbalancing:RemoveTags",
      ]
      resources = [
        "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*",
        "arn:aws:elasticloadbalancing:*:*:loadbalancer/net/*/*",
        "arn:aws:elasticloadbalancing:*:*:loadbalancer/app/*/*",
      ]
      conditions = [
        {
          test     = "Null"
          variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
          values   = ["true"]
        },
        {
          test     = "Null"
          variable = "aws:ResourceTag/elbv2.k8s.aws/cluster"
          values   = ["false"]
        }
      ]
    },
    {
      effect = "Allow"
      actions = [
        "elasticloadbalancing:AddTags",
        "elasticloadbalancing:RemoveTags",
      ]
      resources = [
        "arn:aws:elasticloadbalancing:*:*:listener/net/*/*/*",
        "arn:aws:elasticloadbalancing:*:*:listener/app/*/*/*",
        "arn:aws:elasticloadbalancing:*:*:listener-rule/net/*/*/*",
        "arn:aws:elasticloadbalancing:*:*:listener-rule/app/*/*/*",
      ]
    },
    {
      effect = "Allow"
      actions = [
        "elasticloadbalancing:ModifyLoadBalancerAttributes",
        "elasticloadbalancing:SetIpAddressType",
        "elasticloadbalancing:SetSecurityGroups",
        "elasticloadbalancing:SetSubnets",
        "elasticloadbalancing:DeleteLoadBalancer",
        "elasticloadbalancing:ModifyTargetGroup",
        "elasticloadbalancing:ModifyTargetGroupAttributes",
        "elasticloadbalancing:DeleteTargetGroup",
      ]
      resources = ["*"]
      conditions = [
        {
          test     = "Null"
          variable = "aws:ResourceTag/elbv2.k8s.aws/cluster"
          values   = ["false"]
        }
      ]
    },
    {
      effect = "Allow"
      actions = [
        "elasticloadbalancing:RegisterTargets",
        "elasticloadbalancing:DeregisterTargets",
      ]
      resources = ["arn:aws:elasticloadbalancing:*:*:targetgroup/*/*"]
    },
    {
      effect = "Allow"
      actions = [
        "elasticloadbalancing:SetWebAcl",
        "elasticloadbalancing:ModifyListener",
        "elasticloadbalancing:AddListenerCertificates",
        "elasticloadbalancing:RemoveListenerCertificates",
        "elasticloadbalancing:ModifyRule",
      ]
      resources = ["*"]
    }
  ]

  tags = var.tags
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "ARN of the OIDC Provider for EKS"
  value       = module.eks.oidc_provider_arn
}

output "external_secrets_role_arn" {
  description = "IAM role ARN for External Secrets Operator"
  value       = module.external_secrets_irsa.role_arn
}

output "alb_controller_role_arn" {
  description = "IAM role ARN for AWS Load Balancer Controller"
  value       = module.alb_controller_irsa.role_arn
}

output "secrets" {
  description = "Secret ARNs in AWS Secrets Manager"
  value       = module.secrets.secret_arns
  sensitive   = true
}

output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}

# SOC2 Compliance Outputs
output "ebs_kms_key_id" {
  description = "KMS key ID for EBS encryption"
  value       = aws_kms_key.ebs.id
}

output "ebs_kms_key_arn" {
  description = "KMS key ARN for EBS encryption"
  value       = aws_kms_key.ebs.arn
}

output "backup_vault_name" {
  description = "AWS Backup vault name"
  value       = aws_backup_vault.main.name
}

output "backup_plan_id" {
  description = "AWS Backup plan ID"
  value       = aws_backup_plan.daily.id
}

output "soc2_compliance_summary" {
  description = "SOC2 compliance features enabled"
  value = {
    ebs_encryption_enabled    = true
    kms_key_rotation_enabled  = true
    daily_backups_enabled     = true
    backup_retention_days     = 7
    secrets_encryption        = "AWS Secrets Manager (default AWS encryption)"
    eks_control_plane_logging = "Enabled (api, audit, authenticator, controllerManager, scheduler)"
  }
}

