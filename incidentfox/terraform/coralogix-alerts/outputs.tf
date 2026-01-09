# =============================================================================
# Outputs
# =============================================================================

output "alert_ids" {
  description = "Map of alert names to their Coralogix IDs"
  value = {
    payment_error_rate        = coralogix_alert.payment_error_rate.id
    checkout_failures         = coralogix_alert.checkout_failures.id
    ad_service_latency        = coralogix_alert.ad_service_latency.id
    recommendation_latency    = coralogix_alert.recommendation_latency.id
    product_catalog_errors    = coralogix_alert.product_catalog_errors.id
    image_provider_latency    = coralogix_alert.image_provider_latency.id
    frontend_errors           = coralogix_alert.frontend_errors.id
    ad_high_cpu               = coralogix_alert.ad_high_cpu.id
    email_memory_pressure     = coralogix_alert.email_memory_pressure.id
    kafka_consumer_lag        = coralogix_alert.kafka_consumer_lag.id
    pod_restarts              = coralogix_alert.pod_restarts.id
    traffic_spike             = coralogix_alert.traffic_spike.id
    payment_error_rate_metric = coralogix_alert.payment_error_rate_metric.id
  }
}

output "scenario_to_alerts" {
  description = "Mapping of failure scenarios to their corresponding alerts"
  value = {
    "payment-failure" = [
      coralogix_alert.payment_error_rate.name,
      coralogix_alert.payment_error_rate_metric.name,
      coralogix_alert.checkout_failures.name
    ]
    "high-cpu" = [
      coralogix_alert.ad_high_cpu.name,
      coralogix_alert.ad_service_latency.name
    ]
    "cache-failure" = [
      coralogix_alert.recommendation_latency.name
    ]
    "catalog-failure" = [
      coralogix_alert.product_catalog_errors.name,
      coralogix_alert.checkout_failures.name
    ]
    "memory-leak" = [
      coralogix_alert.email_memory_pressure.name
    ]
    "latency-spike" = [
      coralogix_alert.image_provider_latency.name
    ]
    "kafka-lag" = [
      coralogix_alert.kafka_consumer_lag.name
    ]
    "traffic-spike" = [
      coralogix_alert.traffic_spike.name
    ]
  }
}

