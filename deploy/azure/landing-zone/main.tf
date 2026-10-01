# Mini Azure landing zone for the demo: the management-group hierarchy of the
# Azure Landing Zones reference design, without the costly platform networking.
#
#   Tenant Root Group
#   └── otel-demo-alz
#       ├── platform
#       └── landingzones
#           ├── corp    → lz-corp-prod          (sample resources below)
#           └── online  → lz-online-prod        (the otel-demo AKS app)
#                       → lz-online-dev         (sample resources below)
#
# Sherlocks reads it all through Reader at otel-demo-alz, like an enterprise tenant.

terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  subscription_id = var.online_subscription_id
}

provider "azurerm" {
  alias = "corp"
  features {}
  subscription_id = var.corp_subscription_id
}

provider "azurerm" {
  alias = "online_dev"
  features {}
  subscription_id = var.online_dev_subscription_id
}

data "azurerm_client_config" "current" {}

# ---------------------------------------------------------------------------
# Management groups
# ---------------------------------------------------------------------------

resource "azurerm_management_group" "alz" {
  name         = "otel-demo-alz"
  display_name = "otel-demo ALZ"
}

resource "azurerm_management_group" "platform" {
  name                       = "otel-demo-platform"
  display_name               = "Platform"
  parent_management_group_id = azurerm_management_group.alz.id
}

resource "azurerm_management_group" "landingzones" {
  name                       = "otel-demo-landingzones"
  display_name               = "Landing Zones"
  parent_management_group_id = azurerm_management_group.alz.id
}

resource "azurerm_management_group" "corp" {
  name                       = "otel-demo-corp"
  display_name               = "Corp"
  parent_management_group_id = azurerm_management_group.landingzones.id
}

resource "azurerm_management_group" "online" {
  name                       = "otel-demo-online"
  display_name               = "Online"
  parent_management_group_id = azurerm_management_group.landingzones.id
}

resource "azurerm_management_group_subscription_association" "corp" {
  management_group_id = azurerm_management_group.corp.id
  subscription_id     = "/subscriptions/${var.corp_subscription_id}"
}

resource "azurerm_management_group_subscription_association" "online" {
  management_group_id = azurerm_management_group.online.id
  subscription_id     = "/subscriptions/${var.online_subscription_id}"
}

resource "azurerm_management_group_subscription_association" "online_dev" {
  management_group_id = azurerm_management_group.online.id
  subscription_id     = "/subscriptions/${var.online_dev_subscription_id}"
}

# Sherlocks sees every subscription and the hierarchy below otel-demo-alz.
resource "azurerm_role_assignment" "sherlocks_reader" {
  scope                = azurerm_management_group.alz.id
  role_definition_name = "Reader"
  principal_id         = var.sherlocks_principal_id
}

# ---------------------------------------------------------------------------
# Sample workload in the Corp landing zone (cheap: storage, Key Vault, free App Service)
# ---------------------------------------------------------------------------

resource "azurerm_resource_group" "corp_app" {
  provider = azurerm.corp
  name     = "corp-billing-rg"
  location = var.location
  tags     = var.tags
}

resource "azurerm_storage_account" "corp" {
  provider                        = azurerm.corp
  name                            = "corpbilling${substr(var.corp_subscription_id, 0, 8)}"
  resource_group_name             = azurerm_resource_group.corp_app.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = false
  tags                            = var.tags
}

resource "azurerm_key_vault" "corp" {
  provider                   = azurerm.corp
  name                       = "corp-billing-${substr(var.corp_subscription_id, 0, 8)}"
  resource_group_name        = azurerm_resource_group.corp_app.name
  location                   = var.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  tags                       = var.tags
}

resource "azurerm_service_plan" "corp" {
  provider            = azurerm.corp
  name                = "corp-billing-plan"
  resource_group_name = azurerm_resource_group.corp_app.name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "F1"
  tags                = var.tags
}

resource "azurerm_linux_web_app" "corp" {
  provider            = azurerm.corp
  name                = "corp-billing-api-${substr(var.corp_subscription_id, 0, 8)}"
  resource_group_name = azurerm_resource_group.corp_app.name
  location            = var.location
  service_plan_id     = azurerm_service_plan.corp.id
  tags                = var.tags
  site_config {
    always_on = false # not available on the free tier
  }
}

# ---------------------------------------------------------------------------
# Sample workload in the Online landing zone's dev subscription (same cheap set as Corp)
# ---------------------------------------------------------------------------

resource "azurerm_resource_group" "online_dev_app" {
  provider = azurerm.online_dev
  name     = "online-dev-rg"
  location = var.location
  tags     = var.tags
}

resource "azurerm_storage_account" "online_dev" {
  provider                        = azurerm.online_dev
  name                            = "onlinedev${substr(var.online_dev_subscription_id, 0, 8)}"
  resource_group_name             = azurerm_resource_group.online_dev_app.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = false
  tags                            = var.tags
}

resource "azurerm_key_vault" "online_dev" {
  provider                   = azurerm.online_dev
  name                       = "online-dev-${substr(var.online_dev_subscription_id, 0, 8)}"
  resource_group_name        = azurerm_resource_group.online_dev_app.name
  location                   = var.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  tags                       = var.tags
}

resource "azurerm_service_plan" "online_dev" {
  provider            = azurerm.online_dev
  name                = "online-dev-plan"
  resource_group_name = azurerm_resource_group.online_dev_app.name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "F1"
  tags                = var.tags
}

resource "azurerm_linux_web_app" "online_dev" {
  provider            = azurerm.online_dev
  name                = "online-dev-api-${substr(var.online_dev_subscription_id, 0, 8)}"
  resource_group_name = azurerm_resource_group.online_dev_app.name
  location            = var.location
  service_plan_id     = azurerm_service_plan.online_dev.id
  tags                = var.tags
  site_config {
    always_on = false # not available on the free tier
  }
}
