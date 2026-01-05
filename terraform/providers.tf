# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
}

provider "azuread" {}

provider "random" {}

provider "local" {}
