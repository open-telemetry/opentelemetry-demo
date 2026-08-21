aws_region   = "ap-south-1"
project_name = "otel-demo"
environment  = "dev"

vpc_cidr = "10.0.0.0/16"

az_count = 2

node_instance_types = ["t3.large"]

node_min_size     = 2
node_desired_size = 2
node_max_size     = 4