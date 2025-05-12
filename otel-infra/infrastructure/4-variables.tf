variable "vpc_cidr" {
  description   = "CIDR Block for VPC"
  type          = string
  default       = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "private_subnet_cidrs" {
  description   = "CIDR blocks for private subnets"
  type          = list(string)
  default       = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}


variable "public_subnet_cidrs" {
  description   = "CIDR blocks for public subnets"
  type          = list(string)
  default       = ["10.0.4.0/24", "10.0.5.0/24", "10.0.6.0/24"]
}


variable "cluster_name" {
  description   = "Name of the EKS cluster"
  type          = string
  default       = "otel-cluster"
}

variable "cluster_version" {
  description   = "Kubernetes version"
  type          = string
  default       = "1.30"
}


variable "node_groups" {
  description = "EKS node groups configuration"
  type = map(object({
    instance_types = list(string)
    capacity_type  = string
    scaling_config = object({
      desired_size = number
      max_size     = number
      min_size     = number 
    })
  }))

  default = {
    default = {
      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"
      scaling_config = {
        desired_size = 2
        max_size     = 3
        min_size     = 2
      }
    }
  }
}
