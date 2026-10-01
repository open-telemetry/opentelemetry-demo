# Where alerts go: one Slack channel, via an incoming webhook.
resource "swo_notification" "slack" {
  title       = "otel-demo alerts (Slack)"
  description = "Slack channel for otel-demo alerts"
  type        = "slack"
  settings = {
    slack = {
      url = var.slack_webhook_url
    }
  }
}

locals {
  notify_slack = [
    {
      configuration_ids       = [swo_notification.slack.id] # already "<id>:slack"
      resend_interval_seconds = 3600
    },
  ]
}

# A pod that never became ready for 10 minutes: crash loops (e.g. a bad deploy),
# failing health checks, stuck starts. One alert per pod.
resource "swo_alert" "pod_not_ready" {
  name                  = "otel-demo: pod not ready"
  description           = "A pod in ${var.namespace} has not been ready for 10 minutes (crash loop or failing health check)."
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
      include_tags = [
        { name = "k8s.namespace.name", values = [var.namespace] },
      ]
    },
  ]
}

# A service failing almost every request: e.g. the paymentFailure flag.
resource "swo_alert" "service_errors" {
  name                  = "otel-demo: service error rate"
  description           = "More than ${var.error_rate_threshold_pct}% of a service's traced requests failed over 10 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "composite.trace.service.traced_error_rate"
      aggregation_type    = "AVG"
      threshold           = ">=${var.error_rate_threshold_pct}"
      duration            = "10m"
      group_by_metric_tag = ["service.name"]
      include_tags = [
        { name = "service.name", values = var.services },
      ]
    },
  ]
}

# Requests getting slow: e.g. the imageSlowLoad flag, or a slow dependency.
resource "swo_alert" "service_latency" {
  name                  = "otel-demo: slow requests"
  description           = "Average HTTP server request duration above ${var.latency_threshold_seconds}s over 10 minutes."
  severity              = "WARNING"
  trigger_reset_actions = true
  notification_actions  = local.notify_slack

  conditions = [
    {
      metric_name         = "http.server.request.duration"
      aggregation_type    = "AVG"
      threshold           = ">=${var.latency_threshold_seconds}"
      duration            = "10m"
      group_by_metric_tag = ["service.name"]
      include_tags = [
        { name = "k8s.namespace.name", values = [var.namespace] },
      ]
    },
  ]
}
