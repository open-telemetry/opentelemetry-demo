# The Azure side of the demo: where it runs and where its telemetry goes.

resource "azurerm_resource_group" "demo" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# Log Analytics: the storage behind App Insights and Container Insights.
# daily_quota_gb is the cost guard — ingestion stops for the day once it is reached.
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "otel-demo-logs"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = var.log_analytics_daily_cap_gb
  tags                = var.tags
}

# Application Insights: receives traces, logs and app metrics from the OTel Collector.
resource "azurerm_application_insights" "appi" {
  name                = "otel-demo-appi"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.logs.id
  tags                = var.tags
}

# Container registry: CI pushes the images it builds here.
resource "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

# The Kubernetes cluster the demo runs on.
resource "azurerm_kubernetes_cluster" "aks" {
  name                    = var.aks_name
  resource_group_name     = azurerm_resource_group.demo.name
  location                = azurerm_resource_group.demo.location
  dns_prefix              = var.aks_dns_prefix
  sku_tier                = "Free"
  oidc_issuer_enabled     = true
  node_os_upgrade_channel = "NodeImage"
  tags                    = var.tags

  default_node_pool {
    name            = "nodepool1"
    vm_size         = var.node_vm_size
    node_count      = var.node_count
    os_disk_size_gb = 128

    upgrade_settings {
      max_surge = "10%"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  linux_profile {
    admin_username = "azureuser"
    ssh_key {
      key_data = trimspace(file(pathexpand(var.ssh_public_key_path)))
    }
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    pod_cidr            = "10.244.0.0/16"
    service_cidr        = "10.0.0.0/16"
    dns_service_ip      = "10.0.0.10"
    load_balancer_sku   = "standard"
    outbound_type       = "loadBalancer"
  }

  # Container Insights: pod status, restarts, container logs, Kubernetes events.
  oms_agent {
    log_analytics_workspace_id      = azurerm_log_analytics_workspace.logs.id
    msi_auth_for_monitoring_enabled = true
  }
}

# What Container Insights collects and where it sends it. `az aks create` makes
# these two behind the scenes; Terraform has to declare them explicitly.
resource "azurerm_monitor_data_collection_rule" "container_insights" {
  name                = "MSCI-${var.location}-${var.aks_name}"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  kind                = "Linux"

  destinations {
    log_analytics {
      name                  = "la-workspace"
      workspace_resource_id = azurerm_log_analytics_workspace.logs.id
    }
  }

  data_flow {
    streams      = ["Microsoft-ContainerInsights-Group-Default"]
    destinations = ["la-workspace"]
  }

  data_sources {
    extension {
      name           = "ContainerInsightsExtension"
      extension_name = "ContainerInsights"
      streams        = ["Microsoft-ContainerInsights-Group-Default"]
      extension_json = jsonencode({
        dataCollectionSettings = { enableContainerLogV2 = true }
      })
    }
  }
}

resource "azurerm_monitor_data_collection_rule_association" "container_insights" {
  name                    = "ContainerInsightsExtension"
  description             = "associates dataCollectionRule to the AKS"
  target_resource_id      = azurerm_kubernetes_cluster.aks.id
  data_collection_rule_id = azurerm_monitor_data_collection_rule.container_insights.id
}

# Lets the cluster pull images from the registry.
resource "azurerm_role_assignment" "aks_pull_from_acr" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}
