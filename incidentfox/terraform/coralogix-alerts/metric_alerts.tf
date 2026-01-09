# =============================================================================
# Metric-Based Alerts
# =============================================================================
# These alerts use PromQL queries against metrics flowing to Coralogix

# -----------------------------------------------------------------------------
# 8. Ad Service High CPU (High)
# Triggers: adHighCpu feature flag
# Uses container CPU metrics from Kubernetes
# -----------------------------------------------------------------------------
resource "coralogix_alert" "ad_high_cpu" {
  name        = "Ad Service High CPU"
  description = "Detects high CPU usage in ad service container. Triggers when adHighCpu flag is enabled."
  severity    = "warning"
  enabled     = true

  type_definition {
    metric_threshold {
      metric_filter {
        promql = <<-EOT
          avg(
            rate(container_cpu_usage_seconds_total{container="ad"}[5m])
          ) * 100 > 70
        EOT
      }

      condition {
        condition_type = "more_than"
        threshold      = 70
        timeframe      = "5_min"
        min_non_null_values_percentage = 50
      }

      missing_values {
        replace_with_zero = false
      }
    }
  }

  notification_group {
    group_by_fields = ["coralogix.metadata.sdkId"]
    
    notification {
      integration_id = var.notification_group_id != "" ? var.notification_group_id : null
      notify_on      = "triggered_only"
    }
  }

  labels = merge(local.common_labels, {
    scenario     = "high-cpu"
    trigger_flag = "adHighCpu"
    alert_type   = "infrastructure"
  })
}

# -----------------------------------------------------------------------------
# 9. Email Service Memory Pressure (High)
# Triggers: emailMemoryLeak feature flag
# -----------------------------------------------------------------------------
resource "coralogix_alert" "email_memory_pressure" {
  name        = "Email Service Memory Pressure"
  description = "Detects memory leak in email service. Triggers when emailMemoryLeak flag is enabled."
  severity    = "warning"
  enabled     = true

  type_definition {
    metric_threshold {
      metric_filter {
        promql = <<-EOT
          (
            container_memory_working_set_bytes{container="email"} 
            / 
            container_spec_memory_limit_bytes{container="email"}
          ) * 100 > 80
        EOT
      }

      condition {
        condition_type = "more_than"
        threshold      = 80
        timeframe      = "5_min"
        min_non_null_values_percentage = 50
      }

      missing_values {
        replace_with_zero = false
      }
    }
  }

  notification_group {
    group_by_fields = ["coralogix.metadata.sdkId"]
    
    notification {
      integration_id = var.notification_group_id != "" ? var.notification_group_id : null
      notify_on      = "triggered_only"
    }
  }

  labels = merge(local.common_labels, {
    scenario     = "memory-leak"
    trigger_flag = "emailMemoryLeak"
    alert_type   = "infrastructure"
  })
}

# -----------------------------------------------------------------------------
# 10. Kafka Consumer Lag (High)
# Triggers: kafkaQueueProblems feature flag
# -----------------------------------------------------------------------------
resource "coralogix_alert" "kafka_consumer_lag" {
  name        = "Kafka Consumer Lag"
  description = "Detects growing message backlog in Kafka. Indicates processing delays."
  severity    = "warning"
  enabled     = true

  type_definition {
    metric_threshold {
      metric_filter {
        promql = <<-EOT
          sum(kafka_consumer_group_lag) by (topic) > 1000
        EOT
      }

      condition {
        condition_type = "more_than"
        threshold      = 1000
        timeframe      = "10_min"
        min_non_null_values_percentage = 50
      }

      missing_values {
        replace_with_zero = false
      }
    }
  }

  notification_group {
    group_by_fields = ["coralogix.metadata.sdkId"]
    
    notification {
      integration_id = var.notification_group_id != "" ? var.notification_group_id : null
      notify_on      = "triggered_only"
    }
  }

  labels = merge(local.common_labels, {
    scenario     = "kafka-lag"
    trigger_flag = "kafkaQueueProblems"
    alert_type   = "infrastructure"
  })
}

# -----------------------------------------------------------------------------
# 11. Pod Crash/Restart Detection (Critical)
# Triggers: Any severe failure causing container crashes
# -----------------------------------------------------------------------------
resource "coralogix_alert" "pod_restarts" {
  name        = "OTel Demo Pod Restarts"
  description = "Detects container crashes/restarts in the OTel demo namespace."
  severity    = "critical"
  enabled     = true

  type_definition {
    metric_threshold {
      metric_filter {
        promql = <<-EOT
          increase(kube_pod_container_status_restarts_total{namespace="otel-demo"}[10m]) > 2
        EOT
      }

      condition {
        condition_type = "more_than"
        threshold      = 2
        timeframe      = "10_min"
        min_non_null_values_percentage = 50
      }

      missing_values {
        replace_with_zero = true
      }
    }
  }

  notification_group {
    group_by_fields = ["coralogix.metadata.sdkId"]
    
    notification {
      integration_id = var.notification_group_id != "" ? var.notification_group_id : null
      notify_on      = "triggered_only"
    }
  }

  labels = merge(local.common_labels, {
    scenario   = "pod-crashes"
    alert_type = "infrastructure"
  })
}

# -----------------------------------------------------------------------------
# 12. Traffic Spike Detection (Medium)
# Triggers: loadGeneratorFloodHomepage feature flag
# Uses spanmetrics for request rate
# -----------------------------------------------------------------------------
resource "coralogix_alert" "traffic_spike" {
  name        = "Frontend Traffic Spike"
  description = "Detects unusual traffic volume to frontend. May indicate load test or attack."
  severity    = "info"
  enabled     = true

  type_definition {
    metric_threshold {
      metric_filter {
        promql = <<-EOT
          sum(rate(traces_spanmetrics_calls_total{service_name=~"frontend.*"}[5m])) > 50
        EOT
      }

      condition {
        condition_type = "more_than"
        threshold      = 50  # Adjust based on normal baseline
        timeframe      = "5_min"
        min_non_null_values_percentage = 50
      }

      missing_values {
        replace_with_zero = false
      }
    }
  }

  notification_group {
    group_by_fields = ["coralogix.metadata.sdkId"]
    
    notification {
      integration_id = var.notification_group_id != "" ? var.notification_group_id : null
      notify_on      = "triggered_only"
    }
  }

  labels = merge(local.common_labels, {
    scenario     = "traffic-spike"
    trigger_flag = "loadGeneratorFloodHomepage"
    alert_type   = "traffic"
  })
}

# -----------------------------------------------------------------------------
# 13. Payment Error Rate (Metric-based alternative)
# Uses spanmetrics for error rate calculation
# -----------------------------------------------------------------------------
resource "coralogix_alert" "payment_error_rate_metric" {
  name        = "Payment Service Error Rate (Metric)"
  description = "Metric-based payment error rate using spanmetrics."
  severity    = "critical"
  enabled     = true

  type_definition {
    metric_threshold {
      metric_filter {
        promql = <<-EOT
          (
            sum(rate(traces_spanmetrics_calls_total{service_name=~"payment.*", status_code="STATUS_CODE_ERROR"}[5m]))
            /
            sum(rate(traces_spanmetrics_calls_total{service_name=~"payment.*"}[5m]))
          ) * 100 > 5
        EOT
      }

      condition {
        condition_type = "more_than"
        threshold      = 5  # 5% error rate threshold
        timeframe      = "5_min"
        min_non_null_values_percentage = 50
      }

      missing_values {
        replace_with_zero = false
      }
    }
  }

  notification_group {
    group_by_fields = ["coralogix.metadata.sdkId"]
    
    notification {
      integration_id = var.notification_group_id != "" ? var.notification_group_id : null
      notify_on      = "triggered_only"
    }
  }

  labels = merge(local.common_labels, {
    scenario     = "payment-failure"
    trigger_flag = "paymentFailure"
    alert_type   = "spanmetrics"
  })
}

