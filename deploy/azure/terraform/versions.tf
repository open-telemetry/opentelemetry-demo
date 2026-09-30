# Which Terraform and which plugins ("providers") this setup needs.
#   azurerm = Azure resources (AKS, ACR, App Insights, …)
#   azuread = Microsoft Entra ID objects (the GitHub CI identity)

terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }

  # Terraform's memory (the "state") is kept in an Azure storage account, not on
  # this laptop. Where exactly is set in backend.hcl:
  #   terraform init -backend-config=backend.hcl
  backend "azurerm" {}
}

# Both providers log in with your `az login` session.
provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "azuread" {}
