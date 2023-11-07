# Opensearch OTEL Demo Architecture
This document will review the OpenSearch architecture for the [OTEL demo](https://opentelemetry.io/docs/demo/) and will review how to use the new Observability capabilities
implemented into OpenSearch.
---
This diagram provides an overview of the system components, showcasing the configuration derived from the OpenTelemetry Collector (otelcol) configuration file utilized by the OpenTelemetry demo application.

Additionally, it highlights the observability data (traces and metrics) flow within the system.

![](img/otelcol-data-flow-overview.png)

---
[OTEL DEMO](https://opentelemetry.io/docs/demo/architecture/) Describes the list of services that are composing the Astronomy Shop.

They are combined of:
 - [Accounting](https://opentelemetry.io/docs/demo/services/accounting/)
 - [Ad](https://opentelemetry.io/docs/demo/services/ad/)
 - [Cart](https://opentelemetry.io/docs/demo/services/cart/)
 - [Checkout](https://opentelemetry.io/docs/demo/services/checkout/)
 - [Currency](https://opentelemetry.io/docs/demo/services/currency/)
 - [Email](https://opentelemetry.io/docs/demo/services/email/)
 - [Feature Flag](https://opentelemetry.io/docs/demo/services/feature-flag/)
 - [Fraud Detection](https://opentelemetry.io/docs/demo/services/fraud-detection/)
 - [Frontend](https://opentelemetry.io/docs/demo/services/frontend/)
 - [Kafka](https://opentelemetry.io/docs/demo/services/kafka/)
 - [Payment](https://opentelemetry.io/docs/demo/services/payment/)
 - [Product Catalog](https://opentelemetry.io/docs/demo/services/product-catalog/)
 - [Quote](https://opentelemetry.io/docs/demo/services/quote/)
 - [Recommendation](https://opentelemetry.io/docs/demo/services/recommendation/)
 - [Shipping](https://opentelemetry.io/docs/demo/services/shipping/)
 - [Fluent-Bit](../src/fluent-bit/README.md) *(nginx's otel log exported)* 
 - [Integrations](../src/integrations/README.md) *(pre-canned OpenSearch assets)* 
 - [DataPrepper](../src/dataprepper/README.md) *(OpenSearch's ingestion pipeline)

Backend supportive services
 - [Load Generator](http://load-generator:8089)
   - See [description](https://opentelemetry.io/docs/demo/services/load-generator/)
 - [Frontend Nginx Proxy](http://nginx:90) *(replacement for _Frontend-Proxy_)*
   - See [description](../src/nginx-otel/README.md)
 - [OpenSearch](https://opensearch:9200)
    - See [description](https://github.com/opensearch-project/opentelemetry-demo/blob/12d52cbb23bbf4226f6de2dfec840482a0a7d054/docker-compose.yml#L697)
 - [Dashboards](http://opensearch-dashboards:5601)
   - See [description](https://github.com/opensearch-project/opentelemetry-demo/blob/12d52cbb23bbf4226f6de2dfec840482a0a7d054/docker-compose.yml#L747) 
 - [Prometheus](http://prometheus:9090)
   - See [description](https://github.com/opensearch-project/opentelemetry-demo/blob/12d52cbb23bbf4226f6de2dfec840482a0a7d054/docker-compose.yml#L674)
 - [Feature-Flag](http://feature-flag-service:8881)
   - See [description](../src/featureflagservice/README.md)
 - [Grafana](http://grafana:3000)
   - See [description](https://github.com/opensearch-project/opentelemetry-demo/blob/12d52cbb23bbf4226f6de2dfec840482a0a7d054/docker-compose.yml#L637)

### Services Topology
The next diagram shows the docker compose services dependencies

![](img/docker-services-topology.png)
---

## Purpose
The purpose of this demo is to demonstrate the different capabilities of OpenSearch Observability to investigate and reflect your system.

### Ingestion 
The ingestion capabilities for OpenSearch is to be able to support multiple pipelines:
  - [Data-Prepper](https://github.com/opensearch-project/data-prepper/) is an OpenSearch ingestion project that allows ingestion of OTEL standard signals using Otel-Collector
  - [Jaeger](https://opensearch.org/docs/latest/observing-your-data/trace/trace-analytics-jaeger/) is an ingestion framework which has a build in capability for pushing OTEL signals into OpenSearch
  - [Fluent-Bit](https://docs.fluentbit.io/manual/pipeline/outputs/opensearch) is an ingestion framework which has a build in capability for pushing OTEL signals into OpenSearch

### Integrations -
The integration service is a list of pre-canned assets that are loaded in a combined manner to allow users the ability for simple and automatic way to discover and review their services topology.

These (demo-sample) integrations contain the following assets:
 - components & index template mapping
 - datasources 
 - data-stream & indices
 - queries
 - dashboards
   
Once they are loaded, the user can imminently review his OTEL demo services and dashboards that reflect the system state.
 - [Nginx Dashboard](../src/integrations/display/nginx-logs-dashboard-new.ndjson) - reflects the Nginx Proxy server that routes all the network communication to/from the frontend
 - [Prometheus datasource](../src/integrations/datasource/prometheus.json) - reflects the connectivity to the prometheus metric storage that allows us to federate metrics analytics queries
 - [Logs Datastream](../src/integrations/indices/data-stream.json) - reflects the data-stream used by nginx logs ingestion and dashboards representing a well-structured [log schema](../src/integrations/mapping-templates/logs.mapping)

Once these assets are loaded - the user can start reviewing its Observability dashboards and traces

![Nginx Dashboard](img/nginx_dashboard.png)

![Prometheus Metrics](img/prometheus_federated_metrics.png)

![Trace Analytics](img/trace_analytics.png)

![Service Maps](img/services.png)

![Traces](img/traces.png)

![ServiceGraph](img/service-graph.png)
---

### **Scenarios**

How can you solve problems with OpenTelemetry? These scenarios walk you through some pre-configured problems and show you how to interpret OpenTelemetry data to solve them.

- Generate a Product Catalog error for GetProduct requests with product id: OLJCESPC7Z using the Feature Flag service
- Discover a memory leak and diagnose it using metrics and traces. Read more

### Prometheus Metrics

Getting all metrics names call the following API
`http://localhost:9090/api/v1/label/__name__/values`

This will return the following response:
```json5
{
   "status": "success",
   "data": [
      "app_ads_ad_requests_total",
      "app_currency_counter_total",
      "app_frontend_requests_total",
      "app_payment_transactions_total",
      "app_recommendations_counter_total",
      "http_server_duration_milliseconds_bucket",
      "http_server_duration_milliseconds_count",
      "http_server_duration_milliseconds_sum",
      "kafka_consumer_assigned_partitions",
      "kafka_consumer_bytes_consumed_rate",
      "kafka_consumer_bytes_consumed_total",
      "kafka_consumer_commit_latency_avg",
      "kafka_consumer_commit_latency_max",
      "kafka_consumer_commit_rate",
      "kafka_consumer_commit_sync_time_ns_total",
      "kafka_consumer_commit_total",
      "kafka_consumer_committed_time_ns_total",
      "kafka_consumer_connection_close_rate",
      "kafka_consumer_connection_close_total",
      "kafka_consumer_connection_count",
      "kafka_consumer_connection_creation_rate",
      "kafka_consumer_connection_creation_total",
      "kafka_consumer_failed_authentication_rate",
      "kafka_consumer_failed_authentication_total",
      "kafka_consumer_failed_reauthentication_rate",
      "kafka_consumer_failed_reauthentication_total",
      "kafka_consumer_failed_rebalance_rate_per_hour",
      "kafka_consumer_failed_rebalance_total",
      "kafka_consumer_fetch_latency_avg",
      "kafka_consumer_fetch_latency_max",
      "kafka_consumer_fetch_rate",
      "kafka_consumer_fetch_size_avg",
      "kafka_consumer_fetch_size_max",
      "kafka_consumer_fetch_throttle_time_avg",
      "kafka_consumer_fetch_throttle_time_max",
      "kafka_consumer_fetch_total",
      "kafka_consumer_heartbeat_rate",
      "kafka_consumer_heartbeat_response_time_max",
      "kafka_consumer_heartbeat_total",
      "kafka_consumer_incoming_byte_rate",
      "kafka_consumer_incoming_byte_total",
      "kafka_consumer_io_ratio",
      "kafka_consumer_io_time_ns_avg",
      "kafka_consumer_io_time_ns_total",
      "kafka_consumer_io_wait_ratio",
      "kafka_consumer_io_wait_time_ns_avg",
      "kafka_consumer_io_wait_time_ns_total",
      "kafka_consumer_io_waittime_total",
      "kafka_consumer_iotime_total",
      "kafka_consumer_join_rate",
      "kafka_consumer_join_time_avg",
      "kafka_consumer_join_time_max",
      "kafka_consumer_join_total",
      "kafka_consumer_last_heartbeat_seconds_ago",
      "kafka_consumer_last_poll_seconds_ago",
      "kafka_consumer_last_rebalance_seconds_ago",
      "kafka_consumer_network_io_rate",
      "kafka_consumer_network_io_total",
      "kafka_consumer_outgoing_byte_rate",
      "kafka_consumer_outgoing_byte_total",
      "kafka_consumer_partition_assigned_latency_avg",
      "kafka_consumer_partition_assigned_latency_max",
      "kafka_consumer_partition_lost_latency_avg",
      "kafka_consumer_partition_lost_latency_max",
      "kafka_consumer_partition_revoked_latency_avg",
      "kafka_consumer_partition_revoked_latency_max",
      "kafka_consumer_poll_idle_ratio_avg",
      "kafka_consumer_reauthentication_latency_avg",
      "kafka_consumer_reauthentication_latency_max",
      "kafka_consumer_rebalance_latency_avg",
      "kafka_consumer_rebalance_latency_max",
      "kafka_consumer_rebalance_latency_total",
      "kafka_consumer_rebalance_rate_per_hour",
      "kafka_consumer_rebalance_total",
      "kafka_consumer_records_consumed_rate",
      "kafka_consumer_records_consumed_total",
      "kafka_consumer_records_lag",
      "kafka_consumer_records_lag_avg",
      "kafka_consumer_records_lag_max",
      "kafka_consumer_records_lead",
      "kafka_consumer_records_lead_avg",
      "kafka_consumer_records_lead_min",
      "kafka_consumer_records_per_request_avg",
      "kafka_consumer_request_latency_avg",
      "kafka_consumer_request_latency_max",
      "kafka_consumer_request_rate",
      "kafka_consumer_request_size_avg",
      "kafka_consumer_request_size_max",
      "kafka_consumer_request_total",
      "kafka_consumer_response_rate",
      "kafka_consumer_response_total",
      "kafka_consumer_select_rate",
      "kafka_consumer_select_total",
      "kafka_consumer_successful_authentication_no_reauth_total",
      "kafka_consumer_successful_authentication_rate",
      "kafka_consumer_successful_authentication_total",
      "kafka_consumer_successful_reauthentication_rate",
      "kafka_consumer_successful_reauthentication_total",
      "kafka_consumer_sync_rate",
      "kafka_consumer_sync_time_avg",
      "kafka_consumer_sync_time_max",
      "kafka_consumer_sync_total",
      "kafka_consumer_time_between_poll_avg",
      "kafka_consumer_time_between_poll_max",
      "kafka_controller_active_count",
      "kafka_isr_operation_count",
      "kafka_lag_max",
      "kafka_logs_flush_Count_milliseconds_total",
      "kafka_logs_flush_time_50p_milliseconds",
      "kafka_logs_flush_time_99p_milliseconds",
      "kafka_message_count_total",
      "kafka_network_io_bytes_total",
      "kafka_partition_count",
      "kafka_partition_offline",
      "kafka_partition_underReplicated",
      "kafka_purgatory_size",
      "kafka_request_count_total",
      "kafka_request_failed_total",
      "kafka_request_queue",
      "kafka_request_time_50p_milliseconds",
      "kafka_request_time_99p_milliseconds",
      "kafka_request_time_milliseconds_total",
      "otel_logs_log_processor_logs",
      "otel_logs_log_processor_queue_limit",
      "otel_logs_log_processor_queue_usage",
      "otel_trace_span_processor_queue_limit",
      "otel_trace_span_processor_queue_usage",
      "otel_trace_span_processor_spans",
      "otelcol_exporter_enqueue_failed_log_records",
      "otelcol_exporter_enqueue_failed_metric_points",
      "otelcol_exporter_enqueue_failed_spans",
      "otelcol_exporter_queue_capacity",
      "otelcol_exporter_queue_size",
      "otelcol_exporter_sent_log_records",
      "otelcol_exporter_sent_metric_points",
      "otelcol_exporter_sent_spans",
      "otelcol_process_cpu_seconds",
      "otelcol_process_memory_rss",
      "otelcol_process_runtime_heap_alloc_bytes",
      "otelcol_process_runtime_total_alloc_bytes",
      "otelcol_process_runtime_total_sys_memory_bytes",
      "otelcol_process_uptime",
      "otelcol_processor_accepted_log_records",
      "otelcol_processor_accepted_metric_points",
      "otelcol_processor_accepted_spans",
      "otelcol_processor_batch_batch_send_size_bucket",
      "otelcol_processor_batch_batch_send_size_count",
      "otelcol_processor_batch_batch_send_size_sum",
      "otelcol_processor_batch_timeout_trigger_send",
      "otelcol_processor_dropped_log_records",
      "otelcol_processor_dropped_metric_points",
      "otelcol_processor_dropped_spans",
      "otelcol_processor_refused_log_records",
      "otelcol_processor_refused_metric_points",
      "otelcol_processor_refused_spans",
      "otelcol_processor_servicegraph_expired_edges",
      "otelcol_processor_servicegraph_total_edges",
      "otelcol_receiver_accepted_log_records",
      "otelcol_receiver_accepted_metric_points",
      "otelcol_receiver_accepted_spans",
      "otelcol_receiver_refused_log_records",
      "otelcol_receiver_refused_metric_points",
      "otelcol_receiver_refused_spans",
      "otlp_exporter_exported_total",
      "otlp_exporter_seen_total",
      "process_runtime_dotnet_assemblies_count",
      "process_runtime_dotnet_exceptions_count_total",
      "process_runtime_dotnet_gc_allocations_size_bytes_total",
      "process_runtime_dotnet_gc_collections_count_total",
      "process_runtime_dotnet_gc_committed_memory_size_bytes",
      "process_runtime_dotnet_gc_heap_size_bytes",
      "process_runtime_dotnet_gc_objects_size_bytes",
      "process_runtime_dotnet_jit_compilation_time_nanoseconds_total",
      "process_runtime_dotnet_jit_il_compiled_size_bytes_total",
      "process_runtime_dotnet_jit_methods_compiled_count_total",
      "process_runtime_dotnet_monitor_lock_contention_count_total",
      "process_runtime_dotnet_thread_pool_completed_items_count_total",
      "process_runtime_dotnet_thread_pool_queue_length",
      "process_runtime_dotnet_thread_pool_threads_count",
      "process_runtime_dotnet_timer_count",
      "process_runtime_go_cgo_calls",
      "process_runtime_go_gc_count_total",
      "process_runtime_go_gc_pause_ns_bucket",
      "process_runtime_go_gc_pause_ns_count",
      "process_runtime_go_gc_pause_ns_sum",
      "process_runtime_go_gc_pause_ns_total",
      "process_runtime_go_goroutines",
      "process_runtime_go_mem_heap_alloc_bytes",
      "process_runtime_go_mem_heap_idle_bytes",
      "process_runtime_go_mem_heap_inuse_bytes",
      "process_runtime_go_mem_heap_objects",
      "process_runtime_go_mem_heap_released_bytes",
      "process_runtime_go_mem_heap_sys_bytes",
      "process_runtime_go_mem_live_objects",
      "process_runtime_go_mem_lookups_total",
      "process_runtime_jvm_buffer_count",
      "process_runtime_jvm_buffer_limit_bytes",
      "process_runtime_jvm_buffer_usage_bytes",
      "process_runtime_jvm_classes_current_loaded",
      "process_runtime_jvm_classes_loaded_total",
      "process_runtime_jvm_classes_unloaded_total",
      "process_runtime_jvm_cpu_utilization_ratio",
      "process_runtime_jvm_gc_duration_milliseconds_bucket",
      "process_runtime_jvm_gc_duration_milliseconds_count",
      "process_runtime_jvm_gc_duration_milliseconds_sum",
      "process_runtime_jvm_memory_committed_bytes",
      "process_runtime_jvm_memory_init_bytes",
      "process_runtime_jvm_memory_limit_bytes",
      "process_runtime_jvm_memory_usage_after_last_gc_bytes",
      "process_runtime_jvm_memory_usage_bytes",
      "process_runtime_jvm_system_cpu_load_1m_ratio",
      "process_runtime_jvm_system_cpu_utilization_ratio",
      "process_runtime_jvm_threads_count",
      "processedLogs_total",
      "processedSpans_total",
      "rpc_client_duration_milliseconds_bucket",
      "rpc_client_duration_milliseconds_count",
      "rpc_client_duration_milliseconds_sum",
      "rpc_server_duration_milliseconds_bucket",
      "rpc_server_duration_milliseconds_count",
      "rpc_server_duration_milliseconds_sum",
      "runtime_cpython_cpu_time_seconds_total",
      "runtime_cpython_gc_count_bytes_total",
      "runtime_cpython_memory_bytes_total",
      "runtime_uptime_milliseconds",
      "scrape_duration_seconds",
      "scrape_samples_post_metric_relabeling",
      "scrape_samples_scraped",
      "scrape_series_added",
      "span_metrics_calls_total",
      "span_metrics_duration_milliseconds_bucket",
      "span_metrics_duration_milliseconds_count",
      "span_metrics_duration_milliseconds_sum",
      "system_cpu_time_seconds_total",
      "system_cpu_utilization_ratio",
      "system_disk_io_bytes_total",
      "system_disk_operations_total",
      "system_disk_time_seconds_total",
      "system_memory_usage_bytes",
      "system_memory_utilization_ratio",
      "system_network_connections",
      "system_network_dropped_packets_total",
      "system_network_errors_total",
      "system_network_io_bytes_total",
      "system_network_packets_total",
      "system_swap_usage_pages",
      "system_swap_utilization_ratio",
      "system_thread_count",
      "target_info",
      "up"
   ]
}
```

### **Reference**
Project reference documentation, like requirements and feature matrices [here](https://opentelemetry.io/docs/demo/#reference)

