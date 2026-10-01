# SolarWinds → Logic App (formats the message) → Slack. The Logic App lives in
# the Azure stack (deploy/azure/terraform); its URL is read from that state.
data "terraform_remote_state" "azure" {
  backend = "azurerm"
  config = {
    resource_group_name  = "otel-demo-tfstate-rg"
    storage_account_name = "oteldemotfstateca5de3"
    container_name       = "tfstate"
    key                  = "otel-demo.tfstate"
    use_azuread_auth     = true
  }
}

resource "swo_notification" "logic_app" {
  title       = "otel-demo alerts via Logic App"
  description = "Posts alerts to the otel-demo-solarwinds-to-slack Logic App"
  type        = "webhook"
  settings = {
    webhook = {
      method = "POST"
      url    = data.terraform_remote_state.azure.outputs.solarwinds_webhook_url
      # SolarWinds rejects a webhook without auth settings; the Logic App URL is
      # already signed, so this header is informational only.
      auth_type         = "token"
      auth_header_name  = "X-Source"
      auth_header_value = "otel-demo"
      auth_username     = "" # SolarWinds stores an empty value
    }
  }
}
