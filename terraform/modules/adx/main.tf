# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# =============================================================================
# Azure Data Explorer Cluster
# =============================================================================

resource "azurerm_kusto_cluster" "main" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name

  sku {
    name     = var.sku_name
    capacity = var.sku_capacity
  }

  # Enable streaming ingestion for real-time data
  streaming_ingestion_enabled = true

  # Auto-stop configuration (saves costs when idle)
  auto_stop_enabled = var.auto_stop_enabled

  # Enable purge for data management
  purge_enabled = true

  # Identity for potential managed identity scenarios
  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# =============================================================================
# Database for OpenTelemetry Data
# =============================================================================

resource "azurerm_kusto_database" "otel" {
  name                = var.database_name
  resource_group_name = var.resource_group_name
  location            = var.location
  cluster_name        = azurerm_kusto_cluster.main.name

  # Hot cache for fast queries on recent data
  hot_cache_period = "P${var.hot_cache_days}D"

  # Soft delete retention period (1 year)
  soft_delete_period = "P${var.retention_days}D"
}

# =============================================================================
# Table Schemas for OpenTelemetry Data
# =============================================================================

# Traces Table
resource "azurerm_kusto_script" "traces_table" {
  name                               = "create-traces-table"
  database_id                        = azurerm_kusto_database.otel.id
  continue_on_errors_enabled         = false
  force_an_update_when_value_changed = "v1"

  script_content = <<-EOT
    .create-merge table OTelTraces (
        Timestamp: datetime,
        TraceId: string,
        SpanId: string,
        ParentSpanId: string,
        TraceState: string,
        SpanName: string,
        SpanKind: string,
        ServiceName: string,
        ServiceNamespace: string,
        ServiceInstanceId: string,
        ResourceAttributes: dynamic,
        ScopeName: string,
        ScopeVersion: string,
        SpanAttributes: dynamic,
        Duration: long,
        StatusCode: string,
        StatusMessage: string,
        Events: dynamic,
        Links: dynamic
    )

    .alter-merge table OTelTraces policy retention softdelete = ${var.retention_days}d

    .alter table OTelTraces policy caching hot = ${var.hot_cache_days}d
  EOT
}

# Metrics Table
resource "azurerm_kusto_script" "metrics_table" {
  name                               = "create-metrics-table"
  database_id                        = azurerm_kusto_database.otel.id
  continue_on_errors_enabled         = false
  force_an_update_when_value_changed = "v1"

  script_content = <<-EOT
    .create-merge table OTelMetrics (
        Timestamp: datetime,
        MetricName: string,
        MetricDescription: string,
        MetricUnit: string,
        MetricType: string,
        ServiceName: string,
        ServiceNamespace: string,
        ServiceInstanceId: string,
        ResourceAttributes: dynamic,
        ScopeName: string,
        ScopeVersion: string,
        MetricAttributes: dynamic,
        StartTimestamp: datetime,
        Value: real,
        Count: long,
        Sum: real,
        Min: real,
        Max: real,
        Exemplars: dynamic,
        Buckets: dynamic
    )

    .alter-merge table OTelMetrics policy retention softdelete = ${var.retention_days}d

    .alter table OTelMetrics policy caching hot = ${var.hot_cache_days}d
  EOT

  depends_on = [azurerm_kusto_script.traces_table]
}

# Logs Table
resource "azurerm_kusto_script" "logs_table" {
  name                               = "create-logs-table"
  database_id                        = azurerm_kusto_database.otel.id
  continue_on_errors_enabled         = false
  force_an_update_when_value_changed = "v1"

  script_content = <<-EOT
    .create-merge table OTelLogs (
        Timestamp: datetime,
        ObservedTimestamp: datetime,
        TraceId: string,
        SpanId: string,
        SeverityText: string,
        SeverityNumber: int,
        Body: string,
        ServiceName: string,
        ServiceNamespace: string,
        ServiceInstanceId: string,
        ResourceAttributes: dynamic,
        ScopeName: string,
        ScopeVersion: string,
        LogAttributes: dynamic
    )

    .alter-merge table OTelLogs policy retention softdelete = ${var.retention_days}d

    .alter table OTelLogs policy caching hot = ${var.hot_cache_days}d
  EOT

  depends_on = [azurerm_kusto_script.metrics_table]
}

# =============================================================================
# Ingestion Mappings for OTLP Format
# =============================================================================

resource "azurerm_kusto_script" "ingestion_mappings" {
  name                               = "create-ingestion-mappings"
  database_id                        = azurerm_kusto_database.otel.id
  continue_on_errors_enabled         = false
  force_an_update_when_value_changed = "v1"

  script_content = <<-EOT
    // Traces JSON mapping
    .create-or-alter table OTelTraces ingestion json mapping 'otel_traces_mapping' '[{"column":"Timestamp","path":"$.Timestamp","datatype":"datetime"},{"column":"TraceId","path":"$.TraceId","datatype":"string"},{"column":"SpanId","path":"$.SpanId","datatype":"string"},{"column":"ParentSpanId","path":"$.ParentSpanId","datatype":"string"},{"column":"TraceState","path":"$.TraceState","datatype":"string"},{"column":"SpanName","path":"$.SpanName","datatype":"string"},{"column":"SpanKind","path":"$.SpanKind","datatype":"string"},{"column":"ServiceName","path":"$.ServiceName","datatype":"string"},{"column":"ServiceNamespace","path":"$.ServiceNamespace","datatype":"string"},{"column":"ServiceInstanceId","path":"$.ServiceInstanceId","datatype":"string"},{"column":"ResourceAttributes","path":"$.ResourceAttributes","datatype":"dynamic"},{"column":"ScopeName","path":"$.ScopeName","datatype":"string"},{"column":"ScopeVersion","path":"$.ScopeVersion","datatype":"string"},{"column":"SpanAttributes","path":"$.SpanAttributes","datatype":"dynamic"},{"column":"Duration","path":"$.Duration","datatype":"long"},{"column":"StatusCode","path":"$.StatusCode","datatype":"string"},{"column":"StatusMessage","path":"$.StatusMessage","datatype":"string"},{"column":"Events","path":"$.Events","datatype":"dynamic"},{"column":"Links","path":"$.Links","datatype":"dynamic"}]'

    // Metrics JSON mapping
    .create-or-alter table OTelMetrics ingestion json mapping 'otel_metrics_mapping' '[{"column":"Timestamp","path":"$.Timestamp","datatype":"datetime"},{"column":"MetricName","path":"$.MetricName","datatype":"string"},{"column":"MetricDescription","path":"$.MetricDescription","datatype":"string"},{"column":"MetricUnit","path":"$.MetricUnit","datatype":"string"},{"column":"MetricType","path":"$.MetricType","datatype":"string"},{"column":"ServiceName","path":"$.ServiceName","datatype":"string"},{"column":"ServiceNamespace","path":"$.ServiceNamespace","datatype":"string"},{"column":"ServiceInstanceId","path":"$.ServiceInstanceId","datatype":"string"},{"column":"ResourceAttributes","path":"$.ResourceAttributes","datatype":"dynamic"},{"column":"ScopeName","path":"$.ScopeName","datatype":"string"},{"column":"ScopeVersion","path":"$.ScopeVersion","datatype":"string"},{"column":"MetricAttributes","path":"$.MetricAttributes","datatype":"dynamic"},{"column":"StartTimestamp","path":"$.StartTimestamp","datatype":"datetime"},{"column":"Value","path":"$.Value","datatype":"real"},{"column":"Count","path":"$.Count","datatype":"long"},{"column":"Sum","path":"$.Sum","datatype":"real"},{"column":"Min","path":"$.Min","datatype":"real"},{"column":"Max","path":"$.Max","datatype":"real"},{"column":"Exemplars","path":"$.Exemplars","datatype":"dynamic"},{"column":"Buckets","path":"$.Buckets","datatype":"dynamic"}]'

    // Logs JSON mapping
    .create-or-alter table OTelLogs ingestion json mapping 'otel_logs_mapping' '[{"column":"Timestamp","path":"$.Timestamp","datatype":"datetime"},{"column":"ObservedTimestamp","path":"$.ObservedTimestamp","datatype":"datetime"},{"column":"TraceId","path":"$.TraceId","datatype":"string"},{"column":"SpanId","path":"$.SpanId","datatype":"string"},{"column":"SeverityText","path":"$.SeverityText","datatype":"string"},{"column":"SeverityNumber","path":"$.SeverityNumber","datatype":"int"},{"column":"Body","path":"$.Body","datatype":"string"},{"column":"ServiceName","path":"$.ServiceName","datatype":"string"},{"column":"ServiceNamespace","path":"$.ServiceNamespace","datatype":"string"},{"column":"ServiceInstanceId","path":"$.ServiceInstanceId","datatype":"string"},{"column":"ResourceAttributes","path":"$.ResourceAttributes","datatype":"dynamic"},{"column":"ScopeName","path":"$.ScopeName","datatype":"string"},{"column":"ScopeVersion","path":"$.ScopeVersion","datatype":"string"},{"column":"LogAttributes","path":"$.LogAttributes","datatype":"dynamic"}]'
  EOT

  depends_on = [azurerm_kusto_script.logs_table]
}
