locals {
  notify_slack = [
    {
      # Formatted Slack message via the Logic App (webhook.tf), not SolarWinds'
      # fixed-format Slack integration.
      configuration_ids       = [swo_notification.logic_app.id]
      resend_interval_seconds = 3600
    },
  ]

  this_cluster   = { name = "k8s.cluster.name", values = [var.cluster_name] }
  demo_namespace = { name = "k8s.namespace.name", values = [var.namespace] }
  demo_services  = { name = "service.name", values = var.services }
}

# ---------------------------------------------------------------------------
# Application (traces and HTTP metrics), one alert per service / endpoint
# ---------------------------------------------------------------------------

# An endpoint failing almost every request, e.g. frontend /api/checkout when
# checkout is down, or the paymentFailure flag. Per endpoint, because a fully
# broken endpoint barely moves its service's overall error rate.
resource "swo_alert" "service_errors" {
  name                  = "otel-demo: High Application Error Rate"
  description           = "An endpoint failed at least ${var.error_rate_threshold_pct}% of its requests over 10 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "composite.trace.service.traced_error_rate"
      aggregation_type    = "AVG"
      threshold           = ">=${var.error_rate_threshold_pct}"
      duration            = "10m"
      group_by_metric_tag = ["service.name", "sw.transaction"]
      include_tags        = [local.demo_services]
    },
  ]
}

resource "swo_alert" "service_latency" {
  name                  = "otel-demo: High Application Latency"
  description           = "An endpoint's average request duration was at least ${var.latency_threshold_seconds}s over 10 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "http.server.request.duration"
      aggregation_type    = "AVG"
      threshold           = ">=${var.latency_threshold_seconds}"
      duration            = "10m"
      group_by_metric_tag = ["http.route", "service.name"] # SolarWinds stores these sorted
      include_tags        = [local.this_cluster]
    },
  ]
}

# A dead service cannot report its own errors, so silence is the signal.
resource "swo_alert" "service_silent" {
  name                  = "otel-demo: Service Stopped Reporting"
  description           = "A demo service sent no traced requests for 10 minutes (crashed or down)."
  severity              = "CRITICAL"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "composite.trace.service.traced_request_rate"
      aggregation_type    = "COUNT"
      not_reporting       = true
      duration            = "10m"
      group_by_metric_tag = ["service.name"]
      include_tags        = [local.demo_services]
    },
  ]
}

# ---------------------------------------------------------------------------
# Pods (Kubernetes metrics from the collector), one alert per pod
# ---------------------------------------------------------------------------

resource "swo_alert" "pod_crashloop" {
  name                  = "otel-demo: Pod CrashLoopBackOff"
  description           = "A container has been in CrashLoopBackOff for 5 minutes."
  severity              = "CRITICAL"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "k8s.container.status.reason"
      aggregation_type    = "MAX"
      threshold           = ">=1"
      duration            = "5m"
      group_by_metric_tag = ["k8s.pod.name"]
      include_tags = [
        local.this_cluster,
        local.demo_namespace,
        { name = "k8s.container.status.reason", values = ["CrashLoopBackOff"] },
      ]
    },
  ]
}

# The OOMKilled state itself lasts seconds; the container's last termination
# reason keeps it visible after the restart.
resource "swo_alert" "pod_oom_killed" {
  name                  = "otel-demo: Pod OOM Killed"
  description           = "A container was last restarted because it ran out of memory (OOMKilled)."
  severity              = "CRITICAL"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "k8s.container.restarts"
      aggregation_type    = "MAX"
      threshold           = ">=1"
      duration            = "5m"
      group_by_metric_tag = ["k8s.pod.name"]
      include_tags = [
        local.this_cluster,
        local.demo_namespace,
        { name = "k8s.container.status.last_terminated_reason", values = ["OOMKilled"] },
      ]
    },
  ]
}

resource "swo_alert" "pod_memory_exhaustion" {
  name                  = "otel-demo: Pod Memory Exhaustion (>90% Limit)"
  description           = "A container used more than 90% of its memory limit for 5 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "k8s.container.memory_limit_utilization"
      aggregation_type    = "AVG"
      threshold           = ">=0.9"
      duration            = "5m"
      group_by_metric_tag = ["k8s.pod.name"]
      include_tags        = [local.this_cluster, local.demo_namespace]
      exclude_tags = [
        { name = "k8s.deployment.name", values = var.memory_exhaustion_exclude_deployments },
      ]
    },
  ]
}

resource "swo_alert" "pod_high_cpu" {
  name                  = "otel-demo: Pod High CPU Usage (>1 CPU)"
  description           = "A pod used more than 1 CPU core on average for 5 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "k8s.pod.cpu.usage"
      aggregation_type    = "AVG"
      threshold           = ">=1"
      duration            = "5m"
      group_by_metric_tag = ["k8s.pod.name"]
      include_tags        = [local.this_cluster, local.demo_namespace]
    },
  ]
}

# Pod phase 1 = Pending. MAX <= 1 means the pod stayed Pending the whole window.
resource "swo_alert" "pod_pending" {
  name                  = "otel-demo: Pod Pending (>5m)"
  description           = "A pod has been Pending (not scheduled or not started) for 5 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "k8s.pod.phase"
      aggregation_type    = "MAX"
      threshold           = "<=1"
      duration            = "5m"
      group_by_metric_tag = ["k8s.pod.name"]
      include_tags        = [local.this_cluster, local.demo_namespace]
    },
  ]
}

# A pod never ready for 10 minutes: failing health checks, stuck starts, crashes.
resource "swo_alert" "pod_not_ready" {
  name                  = "otel-demo: Pod Not Ready"
  description           = "A pod has not been ready for 10 minutes (crash loop or failing health check)."
  severity              = "CRITICAL"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "k8s.container.ready"
      aggregation_type    = "MAX"
      threshold           = "<1"
      duration            = "10m"
      group_by_metric_tag = ["k8s.pod.name"]
      include_tags        = [local.this_cluster, local.demo_namespace]
    },
  ]
}

# ---------------------------------------------------------------------------
# Nodes, one alert per node of this cluster
# (no "node not reachable": it would fire on every `demo-stop`)
# ---------------------------------------------------------------------------

resource "swo_alert" "node_not_ready" {
  name                  = "otel-demo: Node Not Ready"
  description           = "A cluster node has not been Ready for 5 minutes."
  severity              = "CRITICAL"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "k8s.node.condition_ready"
      aggregation_type    = "MAX"
      threshold           = "<1"
      duration            = "5m"
      group_by_metric_tag = ["k8s.node.name"]
      include_tags        = [local.this_cluster]
    },
  ]
}

# CPU busy above 80% = idle below 20%.
resource "swo_alert" "node_high_cpu" {
  name                  = "otel-demo: Node High CPU (>80%)"
  description           = "A node's CPU was more than 80% busy on average for 10 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "system.cpu.utilization"
      aggregation_type    = "AVG"
      threshold           = "<=0.2"
      duration            = "10m"
      group_by_metric_tag = ["k8s.node.name"]
      include_tags = [
        local.this_cluster,
        { name = "state", values = ["idle"] },
      ]
    },
  ]
}

resource "swo_alert" "node_high_memory" {
  name                  = "otel-demo: Node High Memory (>85%)"
  description           = "A node's memory was more than 85% used for 10 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "system.memory.utilization"
      aggregation_type    = "AVG"
      threshold           = ">=0.85"
      duration            = "10m"
      group_by_metric_tag = ["k8s.node.name"]
      include_tags = [
        local.this_cluster,
        { name = "state", values = ["used"] },
      ]
    },
  ]
}

resource "swo_alert" "node_disk_pressure" {
  name                  = "otel-demo: Node Disk Pressure (>85%)"
  description           = "A node filesystem was more than 85% full for 10 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "system.filesystem.utilization"
      aggregation_type    = "MAX"
      threshold           = ">=0.85"
      duration            = "10m"
      group_by_metric_tag = ["k8s.node.name", "mountpoint"]
      include_tags        = [local.this_cluster]
    },
  ]
}
