output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS API endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_security_group_id" {
  description = "EKS cluster security group"
  value       = module.eks.cluster_security_group_id
}

output "eks_node_security_group_id" {
  description = "EKS node security group"
  value       = module.eks.node_security_group_id
}

output "aws_lb_controller_role_arn" {
  description = "IAM role used by AWS Load Balancer Controller"
  value       = module.aws_lb_controller_pod_identity.iam_role_arn
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}