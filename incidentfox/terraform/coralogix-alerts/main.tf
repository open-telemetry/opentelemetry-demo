# Coralogix Alerts as Code
# 
# This Terraform configuration defines all alerts for the OTel Demo project.
# Each alert maps to a failure scenario from trigger-incident.sh

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    coralogix = {
      source  = "coralogix/coralogix"
      version = "~> 2.0"
    }
  }
}

# Configure the Coralogix provider
# Set these environment variables:
#   CORALOGIX_API_KEY - Your Coralogix API key
#   CORALOGIX_ENV     - Your Coralogix environment (e.g., "EU2", "US1", "AP1")
provider "coralogix" {
  # API key from environment variable CORALOGIX_API_KEY
  # Environment from CORALOGIX_ENV
}

# =============================================================================
# Local Variables
# =============================================================================

locals {
  # Common labels for all alerts
  common_labels = {
    environment = "lab"
    project     = "incidentfox"
    managed_by  = "terraform"
  }
  
  # Alert notification group (configure your incident.io webhook ID here)
  notification_group_id = var.notification_group_id
}

# =============================================================================
# Variables
# =============================================================================

variable "notification_group_id" {
  description = "Coralogix notification group ID for incident.io integration"
  type        = string
  default     = ""  # Set this or use -var flag
}

variable "environment" {
  description = "Environment name (lab, staging, production)"
  type        = string
  default     = "lab"
}

