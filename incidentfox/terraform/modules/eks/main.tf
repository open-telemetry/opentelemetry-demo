# EKS Module: Creates EKS cluster with managed node groups
# Note: This is a simplified module. For production, consider using terraform-aws-modules/eks/aws

data "aws_iam_policy_document" "cluster_assume_role" {
  statement {
    effect = "Allow"
    
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
    
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${var.cluster_name}-cluster-role"
  assume_role_policy = data.aws_iam_policy_document.cluster_assume_role.json
  
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

resource "aws_iam_role_policy_attachment" "cluster_vpc_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.cluster.name
}

# EKS Cluster
resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn
  
  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
  }
  
  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  
  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
    aws_iam_role_policy_attachment.cluster_vpc_policy,
  ]
  
  tags = var.tags
}

# OIDC Provider for IRSA
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  count = var.enable_irsa ? 1 : 0
  
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
  
  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-irsa"
    }
  )
}

# Node IAM Role
data "aws_iam_policy_document" "node_assume_role" {
  statement {
    effect = "Allow"
    
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
    
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "node" {
  name               = "${var.cluster_name}-node-role"
  assume_role_policy = data.aws_iam_policy_document.node_assume_role.json
  
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_registry_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_ebs_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  role       = aws_iam_role.node.name
}

# Managed Node Groups
resource "aws_eks_node_group" "main" {
  for_each = var.node_groups
  
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.cluster_name}-${each.key}"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  
  capacity_type  = each.value.capacity_type
  instance_types = each.value.instance_types
  
  scaling_config {
    desired_size = each.value.desired_size
    max_size     = each.value.max_size
    min_size     = each.value.min_size
  }
  
  update_config {
    max_unavailable = 1
  }
  
  # SOC2 Compliance: Encryption enabled via KMS key in launch template
  # Specify ami_type to let EKS select compatible AMI
  ami_type = "AL2_x86_64"
  
  # Only use launch template if encryption is enabled
  dynamic "launch_template" {
    for_each = var.enable_ebs_encryption ? [1] : []
    content {
      name    = aws_launch_template.node[each.key].name
      version = "$Latest"
    }
  }
  
  # Disk size (only used if no launch template)
  disk_size = var.enable_ebs_encryption ? null : var.disk_size
  
  labels = each.value.labels
  
  dynamic "taint" {
    for_each = each.value.taints
    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = taint.value.effect
    }
  }
  
  depends_on = [
    aws_iam_role_policy_attachment.node_policy,
    aws_iam_role_policy_attachment.node_cni_policy,
    aws_iam_role_policy_attachment.node_registry_policy,
    aws_iam_role_policy_attachment.node_ebs_policy,
  ]
  
  tags = merge(
    var.tags,
    {
      Name            = "${var.cluster_name}-${each.key}"
      BackupRequired  = "true"  # Tag for AWS Backup selection
      Compliance      = "SOC2"
    }
  )
}

# SOC2: Launch Template with Encrypted EBS
# Only create if encryption is enabled
resource "aws_launch_template" "node" {
  for_each = var.enable_ebs_encryption ? var.node_groups : {}
  
  name_prefix = "${var.cluster_name}-${each.key}-"
  description = "Launch template for ${each.key} node group with encrypted EBS"
  
  # Don't specify image_id - let EKS auto-select the correct AMI
  
  block_device_mappings {
    device_name = "/dev/xvda"
    
    ebs {
      volume_size           = var.disk_size
      volume_type           = "gp3"
      iops                  = 3000
      throughput            = 125
      encrypted             = true
      kms_key_id            = var.ebs_kms_key_id
      delete_on_termination = true
    }
  }
  
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"  # IMDSv2 required (security best practice)
    http_put_response_hop_limit = 2
  }
  
  tag_specifications {
    resource_type = "instance"
    tags = merge(
      var.tags,
      {
        Name       = "${var.cluster_name}-${each.key}-node"
        Compliance = "SOC2"
      }
    )
  }
  
  tag_specifications {
    resource_type = "volume"
    tags = merge(
      var.tags,
      {
        Name           = "${var.cluster_name}-${each.key}-volume"
        BackupRequired = "true"
        Compliance     = "SOC2"
        "kubernetes.io/cluster/${var.cluster_name}" = "owned"
      }
    )
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-${each.key}-template"
    }
  )
}

# Cluster Add-ons
resource "aws_eks_addon" "main" {
  for_each = var.cluster_addons
  
  cluster_name = aws_eks_cluster.main.name
  addon_name   = each.key
  
  addon_version            = each.value.most_recent ? null : each.value.version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "PRESERVE"
  
  tags = var.tags
}

