locals {
  name = "${var.project_name}-${var.environment}"

  azs = slice(
    data.aws_availability_zones.available.names,
    0,
    var.az_count
  )

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}