# =============================================================================
# Alert Definitions
# =============================================================================
# Each alert maps to a failure scenario from trigger-incident.sh
# Alerts are designed to be SILENT during normal operation and FIRE on failure

# -----------------------------------------------------------------------------
# 1. Payment Error Rate (Critical)
# Triggers: paymentFailure feature flag
# -----------------------------------------------------------------------------
resource "coralogix_alert" "payment_error_rate" {
  name        = "Payment Service Error Rate"
  description = "Detects elevated error rate in payment service. Triggers when paymentFailure flag is enabled."
  severity    = "critical"
  enabled     = true

  type_definition {
    tracing_threshold {
      tracing_query {
        latency_threshold_ms = null
        applications         = []
        subsystems           = []
        services             = ["payment", "paymentservice"]
        operations           = []
        tags = []
      }
      
      condition {
        condition_type = "more_than"
        threshold      = 5
        timeframe      = "5_min"
      }
      
      alert_definition_type = "error_count"
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
  })
}

# -----------------------------------------------------------------------------
# 2. Checkout Service Failures (Critical)
# Triggers: Any upstream failure (payment, catalog, cart)
# -----------------------------------------------------------------------------
resource "coralogix_alert" "checkout_failures" {
  name        = "Checkout Service Failures"
  description = "Detects errors in checkout/order placement. Cascades from payment/catalog failures."
  severity    = "critical"
  enabled     = true

  type_definition {
    tracing_threshold {
      tracing_query {
        latency_threshold_ms = null
        applications         = []
        subsystems           = []
        services             = ["checkout", "checkoutservice"]
        operations           = ["PlaceOrder"]
        tags = []
      }
      
      condition {
        condition_type = "more_than"
        threshold      = 3
        timeframe      = "5_min"
      }
      
      alert_definition_type = "error_count"
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
    scenario = "checkout-failure"
  })
}

# -----------------------------------------------------------------------------
# 3. Ad Service Latency Spike (High)
# Triggers: adHighCpu feature flag
# -----------------------------------------------------------------------------
resource "coralogix_alert" "ad_service_latency" {
  name        = "Ad Service Latency Spike"
  description = "Detects high latency in ad service. Triggers when adHighCpu flag causes CPU-bound delays."
  severity    = "warning"
  enabled     = true

  type_definition {
    tracing_threshold {
      tracing_query {
        latency_threshold_ms = 500  # Alert when latency > 500ms
        applications         = []
        subsystems           = []
        services             = ["ad", "adservice"]
        operations           = []
        tags = []
      }
      
      condition {
        condition_type = "more_than"
        threshold      = 10  # More than 10 slow spans
        timeframe      = "5_min"
      }
      
      alert_definition_type = "latency"
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
  })
}

# -----------------------------------------------------------------------------
# 4. Recommendation Service Latency (High)
# Triggers: recommendationCacheFailure feature flag
# -----------------------------------------------------------------------------
resource "coralogix_alert" "recommendation_latency" {
  name        = "Recommendation Service Latency"
  description = "Detects elevated latency when recommendation cache is bypassed."
  severity    = "warning"
  enabled     = true

  type_definition {
    tracing_threshold {
      tracing_query {
        latency_threshold_ms = 300
        applications         = []
        subsystems           = []
        services             = ["recommendation", "recommendationservice"]
        operations           = ["ListRecommendations"]
        tags = []
      }
      
      condition {
        condition_type = "more_than"
        threshold      = 10
        timeframe      = "5_min"
      }
      
      alert_definition_type = "latency"
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
    scenario     = "cache-failure"
    trigger_flag = "recommendationCacheFailure"
  })
}

# -----------------------------------------------------------------------------
# 5. Product Catalog Error Rate (Critical)
# Triggers: productCatalogFailure feature flag
# -----------------------------------------------------------------------------
resource "coralogix_alert" "product_catalog_errors" {
  name        = "Product Catalog Error Rate"
  description = "Detects errors in product catalog service affecting product lookups."
  severity    = "critical"
  enabled     = true

  type_definition {
    tracing_threshold {
      tracing_query {
        latency_threshold_ms = null
        applications         = []
        subsystems           = []
        services             = ["product-catalog", "productcatalogservice"]
        operations           = []
        tags = []
      }
      
      condition {
        condition_type = "more_than"
        threshold      = 5
        timeframe      = "5_min"
      }
      
      alert_definition_type = "error_count"
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
    scenario     = "catalog-failure"
    trigger_flag = "productCatalogFailure"
  })
}

# -----------------------------------------------------------------------------
# 6. Image Provider Latency (Medium)
# Triggers: imageSlowLoad feature flag
# -----------------------------------------------------------------------------
resource "coralogix_alert" "image_provider_latency" {
  name        = "Image Provider Slow Load"
  description = "Detects slow image loading affecting frontend user experience."
  severity    = "info"
  enabled     = true

  type_definition {
    tracing_threshold {
      tracing_query {
        latency_threshold_ms = 3000  # 3 second threshold
        applications         = []
        subsystems           = []
        services             = ["image-provider", "imageprovider"]
        operations           = []
        tags = []
      }
      
      condition {
        condition_type = "more_than"
        threshold      = 5
        timeframe      = "5_min"
      }
      
      alert_definition_type = "latency"
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
    scenario     = "latency-spike"
    trigger_flag = "imageSlowLoad"
  })
}

# -----------------------------------------------------------------------------
# 7. Frontend Error Rate (High)
# Triggers: Any upstream failure (cascading)
# -----------------------------------------------------------------------------
resource "coralogix_alert" "frontend_errors" {
  name        = "Frontend Error Rate"
  description = "Detects elevated errors in frontend service, often cascading from backend issues."
  severity    = "warning"
  enabled     = true

  type_definition {
    tracing_threshold {
      tracing_query {
        latency_threshold_ms = null
        applications         = []
        subsystems           = []
        services             = ["frontend", "frontendservice"]
        operations           = []
        tags = []
      }
      
      condition {
        condition_type = "more_than"
        threshold      = 10
        timeframe      = "5_min"
      }
      
      alert_definition_type = "error_count"
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
    scenario = "frontend-cascade"
  })
}

