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

data "azurerm_client_config" "current" {}

locals {
  # Logic App expressions over the common alert schema.
  essentials = "triggerBody()?['data']?['essentials']"
  condition  = "triggerBody()?['data']?['alertContext']?['condition']?['allOf']?[0]"
  props      = "triggerBody()?['data']?['customProperties']"
  fired      = "equals(${local.essentials}?['monitorCondition'], 'Fired')"

  # Portal pages the "Open …" buttons point to (set per alert as custom properties).
  portal             = "https://portal.azure.com/#@${data.azurerm_client_config.current.tenant_id}/resource"
  appi_failures      = "${local.portal}${azurerm_application_insights.appi.id}/failures"
  appi_performance   = "${local.portal}${azurerm_application_insights.appi.id}/performance"
  container_insights = "${local.portal}${azurerm_kubernetes_cluster.aks.id}/infrainsights"
  aks_metrics        = "${local.portal}${azurerm_kubernetes_cluster.aks.id}/metrics"

  operator_symbol = "replace(replace(replace(replace(coalesce(${local.condition}?['operator'], ''), 'GreaterThanOrEqual', '≥'), 'LessThanOrEqual', '≤'), 'GreaterThan', '>'), 'LessThan', '<')"

  slack_message = {
    text = "@{if(${local.fired}, 'FIRING', 'RESOLVED')}: @{${local.essentials}?['alertRule']}"
    blocks = [
      {
        type = "header"
        text = {
          type  = "plain_text"
          emoji = true
          text  = "@{if(${local.fired}, ':red_circle: FIRING', ':large_green_circle: RESOLVED')} · @{replace(${local.essentials}?['alertRule'], 'otel-demo - ', '')}"
        }
      },
      {
        type = "section"
        fields = [
          { type = "mrkdwn", text = "*Affected*\n@{body('join-dimensions')}" },
          { type = "mrkdwn", text = "*Value*\n@{formatNumber(float(coalesce(${local.condition}?['metricValue'], 0)), '#,##0.##')} @{coalesce(${local.props}?['unit'], '')}  _(threshold @{${local.operator_symbol}} @{${local.condition}?['threshold']} @{coalesce(${local.props}?['unit'], '')})_" },
          { type = "mrkdwn", text = "*Severity*\n@{replace(replace(replace(replace(${local.essentials}?['severity'], 'Sev0', 'Critical'), 'Sev1', 'Error'), 'Sev2', 'Warning'), 'Sev3', 'Info')}" },
          { type = "mrkdwn", text = "*@{if(${local.fired}, 'Fired', 'Resolved')}*\n@{convertFromUtc(if(${local.fired}, ${local.essentials}?['firedDateTime'], coalesce(${local.essentials}?['resolvedDateTime'], utcNow())), 'India Standard Time', 'dd MMM, HH:mm')} IST" },
        ]
      },
      {
        type     = "context"
        elements = [{ type = "mrkdwn", text = "Azure Monitor · ${var.aks_name} · @{${local.essentials}?['description']}" }]
      },
      {
        type = "actions"
        elements = [
          { type = "button", action_id = "view-alert", text = { type = "plain_text", text = "View alert" }, url = "https://portal.azure.com/#view/Microsoft_Azure_Monitoring_Alerts/AlertDetails.ReactView/alertId/@{encodeUriComponent(${local.essentials}?['alertId'])}" },
          { type = "button", action_id = "open-data", text = { type = "plain_text", text = "@{if(empty(${local.condition}?['linkToFilteredSearchResultsUI']), 'Open metrics', 'Open query results')}" }, url = "@{coalesce(${local.condition}?['linkToFilteredSearchResultsUI'], ${local.props}?['metrics_url'], ${local.props}?['dashboard_url'])}" },
          { type = "button", action_id = "open-dashboard", text = { type = "plain_text", text = "Open dashboard" }, url = "@{${local.props}?['dashboard_url']}" },
        ]
      },
    ]
  }
}

# "Affected" lines: the alert's dimensions as "*Name:* value", one per line.
resource "azurerm_logic_app_action_custom" "select_dimensions" {
  name         = "select-dimensions"
  logic_app_id = azurerm_logic_app_workflow.slack.id
  body = jsonencode({
    type     = "Select"
    runAfter = {}
    inputs = {
      from   = "@coalesce(${local.condition}?['dimensions'], json('[]'))"
      select = "@concat('*', toUpper(substring(item()?['name'], 0, 1)), substring(item()?['name'], 1), ':* ', item()?['value'])"
    }
  })
}

resource "azurerm_logic_app_action_custom" "join_dimensions" {
  name         = "join-dimensions"
  logic_app_id = azurerm_logic_app_workflow.slack.id
  body = jsonencode({
    type     = "Join"
    runAfter = { "select-dimensions" = ["Succeeded"] }
    inputs   = { from = "@body('select-dimensions')", joinWith = "\n" }
  })
}

resource "azurerm_logic_app_action_http" "post_to_slack" {
  name         = "post-to-slack"
  logic_app_id = azurerm_logic_app_workflow.slack.id
  method       = "POST"
  uri          = var.slack_webhook_url
  headers      = { "Content-Type" = "application/json" }
  body         = jsonencode(local.slack_message)

  run_after {
    action_name   = azurerm_logic_app_action_custom.join_dimensions.name
    action_result = "Succeeded"
  }
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
  demo_requests = "AppRequests | where tostring(Properties['k8s.namespace.name']) == '${var.alert_namespace}' | extend Service = replace_string(AppRoleName, 'opentelemetry-demo.', ''), Operation = Name"
  demo_pods     = "KubePodInventory | where Namespace == '${var.alert_namespace}'"

  log_alerts = {
    app_error_rate = {
      unit        = "%"
      dashboard   = local.appi_failures
      name        = "otel-demo - High Application Error Rate"
      description = "An operation failed at least 90% of its requests over 10 minutes."
      severity    = 2
      window      = "PT10M"
      query       = <<-KQL
        ${local.demo_requests}
        | summarize total = count(), failed = countif(Success == false) by Service, Operation
        | where total >= 5
        | extend error_pct = 100.0 * failed / total
      KQL
      measure     = "error_pct"
      aggregation = "Maximum"
      operator    = "GreaterThanOrEqual"
      threshold   = 90
      dimensions  = ["Service", "Operation"]
    }
    app_latency = {
      unit        = "ms"
      dashboard   = local.appi_performance
      name        = "otel-demo - High Application Latency"
      description = "An operation's average request duration was at least 500 ms over 10 minutes."
      severity    = 2
      window      = "PT10M"
      query       = <<-KQL
        ${local.demo_requests}
        | summarize total = count(), avg_ms = avg(DurationMs) by Service, Operation
        | where total >= 5
      KQL
      measure     = "avg_ms"
      aggregation = "Maximum"
      operator    = "GreaterThanOrEqual"
      threshold   = 500
      dimensions  = ["Service", "Operation"]
    }
    pod_crashloop = {
      unit        = "records"
      dashboard   = local.container_insights
      name        = "otel-demo - Pod CrashLoopBackOff"
      description = "A container is in CrashLoopBackOff."
      severity    = 1
      window      = "PT5M"
      query       = "${local.demo_pods} | where ContainerStatusReason == 'CrashLoopBackOff' | extend Pod = Name"
      measure     = null
      aggregation = "Count"
      operator    = "GreaterThan"
      threshold   = 0
      dimensions  = ["Pod"]
    }
    pod_oom_killed = {
      unit        = "records"
      dashboard   = local.container_insights
      name        = "otel-demo - Pod OOM Killed"
      description = "A container's last restart was an OOMKill."
      severity    = 1
      window      = "PT5M"
      query       = "${local.demo_pods} | where tostring(parse_json(ContainerLastStatus).reason) == 'OOMKilled' | extend Pod = Name"
      measure     = null
      aggregation = "Count"
      operator    = "GreaterThan"
      threshold   = 0
      dimensions  = ["Pod"]
    }
    pod_not_ready = {
      unit        = ""
      dashboard   = local.container_insights
      name        = "otel-demo - Pod Not Ready"
      description = "A pod had no running container for 10 minutes."
      severity    = 1
      window      = "PT10M"
      query       = <<-KQL
        ${local.demo_pods}
        | summarize running = countif(ContainerStatus == 'running') by Pod = Name
        | where running == 0
        | extend not_ready = 1
      KQL
      measure     = "not_ready"
      aggregation = "Maximum"
      operator    = "GreaterThan"
      threshold   = 0
      dimensions  = ["Pod"]
    }
    pod_memory_exhaustion = {
      unit        = "% of limit"
      dashboard   = local.container_insights
      name        = "otel-demo - Pod Memory Exhaustion (over 90 pct of limit)"
      description = "A container used more than 90% of its memory limit for 5 minutes (valkey-cart and astronomy-db excluded: they always do)."
      severity    = 2
      window      = "PT5M"
      query       = <<-KQL
        let pods = ${local.demo_pods} | distinct ContainerName, Pod = Name;
        Perf
        | where ObjectName == 'K8SContainer' and CounterName in ('memoryWorkingSetBytes', 'memoryLimitBytes')
        | extend ContainerName = strcat(tostring(split(InstanceName, '/')[-2]), '/', tostring(split(InstanceName, '/')[-1])) // "<pod uid>/<container>", as in KubePodInventory
        | summarize used = avgif(CounterValue, CounterName == 'memoryWorkingSetBytes'),
                    limit = maxif(CounterValue, CounterName == 'memoryLimitBytes') by InstanceName, ContainerName
        | join kind=inner pods on ContainerName
        | where Pod !startswith 'valkey-cart' and Pod !startswith 'astronomy-db'
        | where limit > 0
        | extend used_pct = 100.0 * used / limit
      KQL
      measure     = "used_pct"
      aggregation = "Maximum"
      operator    = "GreaterThanOrEqual"
      threshold   = 90
      dimensions  = ["Pod"]
    }
    pod_high_cpu = {
      unit        = "cores"
      dashboard   = local.container_insights
      name        = "otel-demo - Pod High CPU Usage (over 1 CPU)"
      description = "A pod used more than 1 CPU core on average for 5 minutes."
      severity    = 2
      window      = "PT5M"
      query       = <<-KQL
        let pods = ${local.demo_pods} | distinct ContainerName, Pod = Name;
        Perf
        | where ObjectName == 'K8SContainer' and CounterName == 'cpuUsageNanoCores'
        | extend ContainerName = strcat(tostring(split(InstanceName, '/')[-2]), '/', tostring(split(InstanceName, '/')[-1])) // "<pod uid>/<container>", as in KubePodInventory
        | join kind=inner pods on ContainerName
        | summarize cores = avg(CounterValue) / 1e9 by Pod
      KQL
      measure     = "cores"
      aggregation = "Maximum"
      operator    = "GreaterThanOrEqual"
      threshold   = 1
      dimensions  = ["Pod"]
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
    custom_properties = {
      unit          = each.value.unit
      dashboard_url = each.value.dashboard
    }
  }
}

# ---------------------------------------------------------------------------
# Metric alerts (AKS platform metrics). Not affected by the Log Analytics cap.
# (No "node not reachable": it would fire on every `demo-stop`.)
# ---------------------------------------------------------------------------

locals {
  metric_alerts = {
    pod_pending = {
      unit        = "pods"
      dashboard   = local.container_insights
      metrics_url = local.aks_metrics
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
      unit        = ""
      dashboard   = local.container_insights
      metrics_url = local.aks_metrics
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
      unit        = "%"
      dashboard   = local.container_insights
      metrics_url = local.aks_metrics
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
      unit        = "%"
      dashboard   = local.container_insights
      metrics_url = local.aks_metrics
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
      unit        = "%"
      dashboard   = local.container_insights
      metrics_url = local.aks_metrics
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
    webhook_properties = {
      unit          = each.value.unit
      dashboard_url = each.value.dashboard
      metrics_url   = each.value.metrics_url
    }
  }
}

# ---------------------------------------------------------------------------
# SolarWinds → Slack. SolarWinds' own Slack integration has a fixed message
# format, so SolarWinds posts to this Logic App (a "webhook" notification,
# deploy/solarwinds) and the Logic App formats the Slack message.
# ---------------------------------------------------------------------------

resource "azurerm_logic_app_workflow" "solarwinds_slack" {
  name                = "otel-demo-solarwinds-to-slack"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  tags                = var.tags
}

resource "azurerm_logic_app_trigger_http_request" "solarwinds_alert" {
  name         = "solarwinds-alert"
  logic_app_id = azurerm_logic_app_workflow.solarwinds_slack.id
  schema       = jsonencode({ type = "object" })
}

locals {
  # SolarWinds sends the alert JSON base64-encoded ("application/octet-stream").
  swo     = "outputs('parse-payload')"
  cleared = "equals(${local.swo}?['severity'], 'CLEAR')"

  swo_slack_message = {
    text = "@{if(${local.cleared}, 'RESOLVED', 'FIRING')}: @{${local.swo}?['name']}"
    blocks = [
      {
        type = "header"
        text = {
          type  = "plain_text"
          emoji = true
          text  = "@{if(${local.cleared}, ':large_green_circle: RESOLVED', if(equals(${local.swo}?['severity'], 'CRITICAL'), ':red_circle: FIRING', ':large_orange_circle: FIRING'))} · @{replace(${local.swo}?['name'], 'otel-demo: ', '')}"
        }
      },
      {
        type = "section"
        fields = [
          { type = "mrkdwn", text = "*Affected*\n@{body('join-tags')}" },
          { type = "mrkdwn", text = "*Value*\n@{formatNumber(float(coalesce(${local.swo}?['metrics']?[0]?['value'], 0)), '#,##0.###')}  _(@{${local.swo}?['condition']})_" },
          { type = "mrkdwn", text = "*Severity*\n@{if(${local.cleared}, 'Resolved', concat(substring(${local.swo}?['severity'], 0, 1), toLower(substring(${local.swo}?['severity'], 1))))}" },
          { type = "mrkdwn", text = "*@{if(${local.cleared}, 'Resolved', 'Fired')}*\n@{convertFromUtc(coalesce(${local.swo}?['clearedAt'], ${local.swo}?['timestamp'], utcNow()), 'India Standard Time', 'dd MMM, HH:mm')} IST@{if(${local.cleared}, concat(' · after ', string(div(coalesce(${local.swo}?['activeDurationInSeconds'], 0), 60)), ' min'), '')}" },
        ]
      },
      {
        type     = "context"
        elements = [{ type = "mrkdwn", text = "SolarWinds Observability · ${var.aks_name} · @{${local.swo}?['description']}" }]
      },
      {
        type = "actions"
        elements = [
          { type = "button", action_id = "view-alert", text = { type = "plain_text", text = "View alert" }, url = "@{${local.swo}?['detailUrl']}" },
          { type = "button", action_id = "open-metrics", text = { type = "plain_text", text = "Open metrics" }, url = "@{coalesce(${local.swo}?['runbook'], ${local.swo}?['detailUrl'])}" },
        ]
      },
    ]
  }
}

resource "azurerm_logic_app_action_custom" "swo_parse" {
  name         = "parse-payload"
  logic_app_id = azurerm_logic_app_workflow.solarwinds_slack.id
  body = jsonencode({
    type     = "Compose"
    runAfter = {}
    inputs   = "@json(base64ToString(triggerBody()?['$content']))"
  })
}

# "Affected" lines from the alert's tags, with readable names.
resource "azurerm_logic_app_action_custom" "swo_select_tags" {
  name         = "select-tags"
  logic_app_id = azurerm_logic_app_workflow.solarwinds_slack.id
  body = jsonencode({
    type     = "Select"
    runAfter = { "parse-payload" = ["Succeeded"] }
    inputs = {
      from   = "@coalesce(${local.swo}?['affectedEvaluations']?[0]?['tags'], ${local.swo}?['tags'], json('[]'))"
      select = "@concat('*', replace(replace(replace(replace(replace(replace(item()?['key'], 'k8s.pod.name', 'Pod'), 'k8s.node.name', 'Node'), 'service.name', 'Service'), 'sw.transaction', 'Endpoint'), 'http.route', 'Route'), 'mountpoint', 'Mount'), ':* ', item()?['value'])"
    }
  })
}

resource "azurerm_logic_app_action_custom" "swo_join_tags" {
  name         = "join-tags"
  logic_app_id = azurerm_logic_app_workflow.solarwinds_slack.id
  body = jsonencode({
    type     = "Join"
    runAfter = { "select-tags" = ["Succeeded"] }
    inputs   = { from = "@body('select-tags')", joinWith = "\n" }
  })
}

resource "azurerm_logic_app_action_http" "swo_post_to_slack" {
  name         = "post-to-slack"
  logic_app_id = azurerm_logic_app_workflow.solarwinds_slack.id
  method       = "POST"
  uri          = var.solarwinds_slack_webhook_url
  headers      = { "Content-Type" = "application/json" }
  body         = jsonencode(local.swo_slack_message)

  run_after {
    action_name   = azurerm_logic_app_action_custom.swo_join_tags.name
    action_result = "Succeeded"
  }
}
