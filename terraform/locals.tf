# =============================================================================
# Local Variables
# =============================================================================

locals {
  resource_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(var.tags, {
    Environment = var.environment
    Project     = var.project_name
  })
}
