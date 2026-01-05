# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# =============================================================================
# Azure Kubernetes Service Cluster
# =============================================================================

resource "azurerm_kubernetes_cluster" "main" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = var.cluster_name
  kubernetes_version  = var.kubernetes_version

  # Default node pool configuration
  default_node_pool {
    name                = var.default_node_pool_name
    vm_size             = var.default_node_pool_vm_size
    node_count          = var.enable_auto_scaling ? null : var.default_node_pool_count
    min_count           = var.enable_auto_scaling ? var.default_node_pool_min_count : null
    max_count           = var.enable_auto_scaling ? var.default_node_pool_max_count : null
    enable_auto_scaling = var.enable_auto_scaling
    vnet_subnet_id      = var.subnet_id

    # Node labels for workload placement
    node_labels = {
      "workload" = "otel-demo"
    }

    # Temporary disk for OS
    os_disk_size_gb = 30
    os_disk_type    = "Managed"
  }

  # System-assigned managed identity for AKS
  identity {
    type = "SystemAssigned"
  }

  # Network configuration
  network_profile {
    network_plugin    = "azure"
    network_policy    = "azure"
    load_balancer_sku = "standard"
    outbound_type     = "loadBalancer"
    service_cidr      = "172.16.0.0/16"
    dns_service_ip    = "172.16.0.10"
  }

  # Azure Monitor integration (optional but recommended)
  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  }

  # RBAC configuration
  role_based_access_control_enabled = true

  azure_active_directory_role_based_access_control {
    managed            = true
    azure_rbac_enabled = true
  }

  # Automatic upgrade channel
  automatic_channel_upgrade = "patch"

  # Maintenance window (weekends, off-hours)
  maintenance_window {
    allowed {
      day   = "Saturday"
      hours = [0, 1, 2, 3, 4, 5]
    }
    allowed {
      day   = "Sunday"
      hours = [0, 1, 2, 3, 4, 5]
    }
  }

  tags = var.tags
}

# =============================================================================
# Log Analytics Workspace for AKS Monitoring
# =============================================================================

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.cluster_name}-logs"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = var.tags
}

# =============================================================================
# Container Insights Solution
# =============================================================================

resource "azurerm_log_analytics_solution" "container_insights" {
  solution_name         = "ContainerInsights"
  location              = var.location
  resource_group_name   = var.resource_group_name
  workspace_resource_id = azurerm_log_analytics_workspace.main.id
  workspace_name        = azurerm_log_analytics_workspace.main.name

  plan {
    publisher = "Microsoft"
    product   = "OMSGallery/ContainerInsights"
  }

  tags = var.tags
}
