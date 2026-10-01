# Same storage account as the Azure Terraform, separate key. When switching
# SolarWinds accounts, change `key` so each account has its own state.
resource_group_name  = "otel-demo-tfstate-rg"
storage_account_name = "oteldemotfstateca5de3"
container_name       = "tfstate"
key                  = "solarwinds-ap-01.tfstate"
use_azuread_auth     = true
