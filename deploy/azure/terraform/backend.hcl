# Where Terraform keeps its state. The storage account lives in its own resource
# group so that deleting the demo never deletes Terraform's memory of it.
resource_group_name  = "otel-demo-tfstate-rg"
storage_account_name = "oteldemotfstateca5de3"
container_name       = "tfstate"
key                  = "otel-demo.tfstate"
use_azuread_auth     = true
