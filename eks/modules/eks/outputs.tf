output "cluster_endpoint" {
  description = "Controlplane public endpoint"
  value = aws_eks_cluster.main.endpoint
}

output "cluster_name" {
  description = "EKS Cluster name"
  value = aws_eks_cluster.main.name
}