# Azure alerts → Slack. Mirrors the SolarWinds alert set (deploy/solarwinds).
#
#   alert rule → action group → Logic App (formats the message) → Slack webhook
#
# Alert names avoid : / # % & * < > ? \\ — Azure rejects them.
#
# Azure posts its own JSON ("common alert schema"), which a Slack webhook does not
# accept, so the Logic App turns it into a Slack message.

# ---------------------------------------------------------------------------
# Delivery: Logic App + action group
# ---------------------------------------------------------------------------

resource "azurerm_logic_app_workflow" "slack" {
  name                = "otel-demo-alerts-to-slack"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  tags                = var.tags
}

resource "azurerm_logic_app_trigger_http_request" "alert" {
  name         = "azure-alert"
  logic_app_id = azurerm_logic_app_workflow.slack.id
  schema       = jsonencode({ type = "object" })
}

locals {
  # Logic App expressions over the common alert schema.
  essentials = "triggerBody()?['data']?['essentials']"
  condition  = "triggerBody()?['data']?['alertContext']?['condition']?['allOf']?[0]"

  slack_text = join("\n", [
    "@{if(equals(${local.essentials}?['monitorCondition'], 'Fired'), ':red_circle: *Fired*', ':large_green_circle: *Resolved*')} · Azure Monitor · *@{${local.essentials}?['alertRule']}*",
    "Severity: @{${local.essentials}?['severity']} · @{${local.essentials}?['description']}",
    "Affected: @{string(${local.condition}?['dimensions'])}",
    "Value: @{${local.condition}?['metricValue']} (threshold @{${local.condition}?['operator']} @{${local.condition}?['threshold']})",
    "Fired at: @{${local.essentials}?['firedDateTime']}",
  ])
}

resource "azurerm_logic_app_action_http" "post_to_slack" {
  name         = "post-to-slack"
  logic_app_id = azurerm_logic_app_workflow.slack.id
  method       = "POST"
  uri          = var.slack_webhook_url
  headers      = { "Content-Type" = "application/json" }
  body         = jsonencode({ text = local.slack_text })
}

resource "azurerm_monitor_action_group" "slack" {
  name                = "otel-demo-slack"
  resource_group_name = azurerm_resource_group.demo.name
  short_name          = "otel-slack"
  tags                = var.tags

  webhook_receiver {
    name                    = "logic-app-to-slack"
    service_uri             = azurerm_logic_app_trigger_http_request.alert.callback_url
    use_common_alert_schema = true
  }
}

# ---------------------------------------------------------------------------
# Log alerts (KQL on Log Analytics: App Insights + Container Insights).
# These stop seeing new data while the daily cap is reached.
# ---------------------------------------------------------------------------

locals {
  demo_requests = "AppRequests | where tostring(Properties['k8s.namespace.name']) == '${var.alert_namespace}'"
  demo_pods     = "KubePodInventory | where Namespace == '${var.alert_namespace}'"

  log_alerts = {
    app_error_rate = {
      name        = "otel-demo - High Application Error Rate"
      description = "An operation failed at least 90% of its requests over 10 minutes."
      severity    = 2
      window      = "PT10M"
      query       = <<-KQL
        ${local.demo_requests}
        | summarize total = count(), failed = countif(Success == false) by AppRoleName, Name
        | where total >= 5
        | extend error_pct = 100.0 * failed / total
      KQL
      measure     = "error_pct"
      aggregation = "Maximum"
      operator    = "GreaterThanOrEqual"
      threshold   = 90
      dimensions  = ["AppRoleName", "Name"]
    }
    app_latency = {
      name        = "otel-demo - High Application Latency"
      description = "An operation's average request duration was at least 500 ms over 10 minutes."
      severity    = 2
      window      = "PT10M"
      query       = <<-KQL
        ${local.demo_requests}
        | summarize total = count(), avg_ms = avg(DurationMs) by AppRoleName, Name
        | where total >= 5
      KQL
      measure     = "avg_ms"
      aggregation = "Maximum"
      operator    = "GreaterThanOrEqual"
      threshold   = 500
      dimensions  = ["AppRoleName", "Name"]
    }
    pod_crashloop = {
      name        = "otel-demo - Pod CrashLoopBackOff"
      description = "A container is in CrashLoopBackOff."
      severity    = 1
      window      = "PT5M"
      query       = "${local.demo_pods} | where ContainerStatusReason == 'CrashLoopBackOff'"
      measure     = null
      aggregation = "Count"
      operator    = "GreaterThan"
      threshold   = 0
      dimensions  = ["Name"]
    }
    pod_oom_killed = {
      name        = "otel-demo - Pod OOM Killed"
      description = "A container's last restart was an OOMKill."
      severity    = 1
      window      = "PT5M"
      query       = "${local.demo_pods} | where tostring(parse_json(ContainerLastStatus).reason) == 'OOMKilled'"
      measure     = null
      aggregation = "Count"
      operator    = "GreaterThan"
      threshold   = 0
      dimensions  = ["Name"]
    }
    pod_not_ready = {
      name        = "otel-demo - Pod Not Ready"
      description = "A pod had no running container for 10 minutes."
      severity    = 1
      window      = "PT10M"
      query       = <<-KQL
        ${local.demo_pods}
        | summarize running = countif(ContainerStatus == 'running') by Name
        | where running == 0
        | extend not_ready = 1
      KQL
      measure     = "not_ready"
      aggregation = "Maximum"
      operator    = "GreaterThan"
      threshold   = 0
      dimensions  = ["Name"]
    }
    pod_memory_exhaustion = {
      name        = "otel-demo - Pod Memory Exhaustion (over 90 pct of limit)"
      description = "A container used more than 90% of its memory limit for 5 minutes (valkey-cart and astronomy-db excluded: they always do)."
      severity    = 2
      window      = "PT5M"
      query       = <<-KQL
        let pods = ${local.demo_pods} | distinct ContainerName, PodName = Name;
        Perf
        | where ObjectName == 'K8SContainer' and CounterName in ('memoryWorkingSetBytes', 'memoryLimitBytes')
        | extend ContainerName = strcat(tostring(split(InstanceName, '/')[-2]), '/', tostring(split(InstanceName, '/')[-1])) // "<pod uid>/<container>", as in KubePodInventory
        | summarize used = avgif(CounterValue, CounterName == 'memoryWorkingSetBytes'),
                    limit = maxif(CounterValue, CounterName == 'memoryLimitBytes') by InstanceName, ContainerName
        | join kind=inner pods on ContainerName
        | where PodName !startswith 'valkey-cart' and PodName !startswith 'astronomy-db'
        | where limit > 0
        | extend used_pct = 100.0 * used / limit
      KQL
      measure     = "used_pct"
      aggregation = "Maximum"
      operator    = "GreaterThanOrEqual"
      threshold   = 90
      dimensions  = ["PodName"]
    }
    pod_high_cpu = {
      name        = "otel-demo - Pod High CPU Usage (over 1 CPU)"
      description = "A pod used more than 1 CPU core on average for 5 minutes."
      severity    = 2
      window      = "PT5M"
      query       = <<-KQL
        let pods = ${local.demo_pods} | distinct ContainerName, PodName = Name;
        Perf
        | where ObjectName == 'K8SContainer' and CounterName == 'cpuUsageNanoCores'
        | extend ContainerName = strcat(tostring(split(InstanceName, '/')[-2]), '/', tostring(split(InstanceName, '/')[-1])) // "<pod uid>/<container>", as in KubePodInventory
        | join kind=inner pods on ContainerName
        | summarize cores = avg(CounterValue) / 1e9 by PodName
      KQL
      measure     = "cores"
      aggregation = "Maximum"
      operator    = "GreaterThanOrEqual"
      threshold   = 1
      dimensions  = ["PodName"]
    }
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "log" {
  for_each = local.log_alerts

  name                    = each.value.name
  description             = each.value.description
  resource_group_name     = azurerm_resource_group.demo.name
  location                = azurerm_resource_group.demo.location
  scopes                  = [azurerm_log_analytics_workspace.logs.id]
  severity                = each.value.severity
  evaluation_frequency    = "PT5M"
  window_duration         = each.value.window
  auto_mitigation_enabled = true # sends "Resolved" when it clears
  tags                    = var.tags

  criteria {
    query                   = each.value.query
    time_aggregation_method = each.value.aggregation
    metric_measure_column   = each.value.measure
    operator                = each.value.operator
    threshold               = each.value.threshold

    dynamic "dimension" {
      for_each = each.value.dimensions
      content {
        name     = dimension.value
        operator = "Include"
        values   = ["*"]
      }
    }

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.slack.id]
  }
}

# ---------------------------------------------------------------------------
# Metric alerts (AKS platform metrics). Not affected by the Log Analytics cap.
# (No "node not reachable": it would fire on every `demo-stop`.)
# ---------------------------------------------------------------------------

locals {
  metric_alerts = {
    pod_pending = {
      name        = "otel-demo - Pod Pending (over 5 min)"
      description = "A pod has been Pending for 5 minutes."
      severity    = 2
      metric      = "kube_pod_status_phase"
      operator    = "GreaterThanOrEqual"
      threshold   = 1
      window      = "PT5M"
      dimensions = [
        { name = "phase", values = ["Pending"] },
        { name = "namespace", values = [var.alert_namespace] },
        { name = "pod", values = ["*"] },
      ]
    }
    node_not_ready = {
      name        = "otel-demo - Node Not Ready"
      description = "A node's Ready condition has not been true for 5 minutes."
      severity    = 1
      metric      = "kube_node_status_condition"
      operator    = "GreaterThan"
      threshold   = 0
      window      = "PT5M"
      dimensions = [
        { name = "condition", values = ["Ready"] },
        { name = "status", values = ["false", "unknown"] },
        { name = "node", values = ["*"] },
      ]
    }
    node_high_cpu = {
      name        = "otel-demo - Node High CPU (over 80 pct)"
      description = "A node's CPU was more than 80% used for 15 minutes."
      severity    = 2
      metric      = "node_cpu_usage_percentage"
      operator    = "GreaterThan"
      threshold   = 80
      window      = "PT15M" # metric alerts allow 1/5/15/30 min windows
      dimensions  = [{ name = "node", values = ["*"] }]
    }
    node_high_memory = {
      name        = "otel-demo - Node High Memory (over 85 pct)"
      description = "A node's memory working set was above 85% for 15 minutes."
      severity    = 2
      metric      = "node_memory_working_set_percentage"
      operator    = "GreaterThan"
      threshold   = 85
      window      = "PT15M" # metric alerts allow 1/5/15/30 min windows
      dimensions  = [{ name = "node", values = ["*"] }]
    }
    node_disk_pressure = {
      name        = "otel-demo - Node Disk Pressure (over 85 pct)"
      description = "A node disk was more than 85% full for 15 minutes."
      severity    = 2
      metric      = "node_disk_usage_percentage"
      operator    = "GreaterThan"
      threshold   = 85
      window      = "PT15M" # metric alerts allow 1/5/15/30 min windows
      dimensions = [
        { name = "node", values = ["*"] },
        { name = "device", values = ["*"] },
      ]
    }
  }
}

resource "azurerm_monitor_metric_alert" "aks" {
  for_each = local.metric_alerts

  name                = each.value.name
  description         = each.value.description
  resource_group_name = azurerm_resource_group.demo.name
  scopes              = [azurerm_kubernetes_cluster.aks.id]
  severity            = each.value.severity
  frequency           = "PT1M"
  window_size         = each.value.window
  auto_mitigate       = true
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = each.value.metric
    aggregation      = "Average"
    operator         = each.value.operator
    threshold        = each.value.threshold

    dynamic "dimension" {
      for_each = each.value.dimensions
      content {
        name     = dimension.value.name
        operator = "Include"
        values   = dimension.value.values
      }
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.slack.id
  }
}
