variable "cluster_name" {
  description = "EKS Cluster name"
  type = string
}

variable "cluster_version" {
  description = "Version of Kubernetes"
  type = string
}

variable "vpc_id" {
  description = "VPC ID where will be created"
  type = string
}

variable "subnet_ids" {
  description = "List of Subnet IDs for our controlplane & worker nodes"
  type = list(string)
}

variable "node_groups" {
  description = "EKS node group configuration"
  type = map(object({
    instance_types = list(string)
    capacity_type  = string
    scaling_config = object({
      desired_size = number
      max_size     = number
      min_size     = number
    })
  }))
}
