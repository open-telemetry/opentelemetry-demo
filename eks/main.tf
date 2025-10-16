provider "aws" {
  region = var.aws_region
}

terraform {
  backend "s3" {
    bucket       = "rajat-terraform-state-bucket"
    key          = "project2/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

module "vpc" {
  source = "./modules/vpc"

  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs

  availability_zones = var.availability_zones

  cluster_name = var.cluster_name
}

module "eks" {
  source = "./modules/eks"

  vpc_id = module.vpc.vpc_id
  cluster_name = var.cluster_name
  cluster_version = var.cluster_version
  subnet_ids = module.vpc.private_subnet_ids
  node_groups = var.node_groups
}