# SolarWinds Observability alerts for the otel-demo, sent to Slack.
#
# The API token comes from the SWO_API_TOKEN environment variable (a *Full
# Access* token, not the ingestion token), loaded from ../secrets.env:
#   set -a; . ../secrets.env; set +a

terraform {
  required_version = ">= 1.9"

  required_providers {
    swo = {
      source  = "solarwinds/swo"
      version = "~> 0.2"
    }
  }

  # State lives next to the Azure Terraform state, under its own key.
  #   terraform init -backend-config=backend.hcl
  backend "azurerm" {}
}

provider "swo" {
  base_url = "https://api.${var.swo_region}.cloud.solarwinds.com/v1/tfproxy"
}
