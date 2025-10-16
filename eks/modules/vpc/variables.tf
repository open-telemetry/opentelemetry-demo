variable "vpc_cidr" {
  description = "CIDR block for our VPC"
  type = string
}

variable "public_subnet_cidrs" {
  description = "List of CIDR blocks for public subnets"
  type = list(string)
}

variable "private_subnet_cidrs" {
  description = "List of CIDR blocks for private subnets"
  type = list(string)
}

variable "availability_zones" {
  description = "List of AZ codes in the VPC region, Must match the size of public & private subnets"
  type = list(string)
}

variable "cluster_name" {
  description = "EKS cluster name"
  type = string
}