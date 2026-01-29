-- =============================================================================
-- Drop Existing Tables (Fresh Install)
-- =============================================================================
DROP TABLE IF EXISTS vast."csnow-db|otel".logs_otel_analytic;
DROP TABLE IF EXISTS vast."csnow-db|otel".metrics_otel_analytic;
DROP TABLE IF EXISTS vast."csnow-db|otel".span_events_otel_analytic;
DROP TABLE IF EXISTS vast."csnow-db|otel".span_links_otel_analytic;
DROP TABLE IF EXISTS vast."csnow-db|otel".traces_otel_analytic;
DROP TABLE IF EXISTS vast."csnow-db|otel".service_baselines;
DROP TABLE IF EXISTS vast."csnow-db|otel".anomaly_scores;
DROP TABLE IF EXISTS vast."csnow-db|otel".alerts;
DROP TABLE IF EXISTS vast."csnow-db|otel".alert_investigations;

-- vast."csnow-db|otel".logs_otel_analytic definition

CREATE TABLE vast."csnow-db|otel".logs_otel_analytic (
   timestamp timestamp(9),
   service_name varchar,
   severity_number integer,
   severity_text varchar,
   body_text varchar,
   trace_id varchar,
   span_id varchar,
   attributes_json varchar
);

-- vast."csnow-db|otel".metrics_otel_analytic definition

CREATE TABLE vast."csnow-db|otel".metrics_otel_analytic (
   timestamp timestamp(9),
   service_name varchar,
   metric_name varchar,
   metric_unit varchar,
   value_double double,
   attributes_flat varchar
);

-- vast."csnow-db|otel".span_events_otel_analytic definition

CREATE TABLE vast."csnow-db|otel".span_events_otel_analytic (
   timestamp timestamp(9),
   trace_id varchar,
   span_id varchar,
   service_name varchar,
   span_name varchar,
   event_name varchar,
   event_attributes_json varchar,
   exception_type varchar,
   exception_message varchar,
   exception_stacktrace varchar,
   gen_ai_system varchar,
   gen_ai_operation varchar,
   gen_ai_request_model varchar,
   gen_ai_usage_prompt_tokens integer,
   gen_ai_usage_completion_tokens integer
);

-- vast."csnow-db|otel".span_links_otel_analytic definition

CREATE TABLE vast."csnow-db|otel".span_links_otel_analytic (
   trace_id varchar,
   span_id varchar,
   service_name varchar,
   span_name varchar,
   linked_trace_id varchar,
   linked_span_id varchar,
   linked_trace_state varchar,
   link_attributes_json varchar
);

-- vast."csnow-db|otel".traces_otel_analytic definition

CREATE TABLE vast."csnow-db|otel".traces_otel_analytic (
   trace_id varchar,
   span_id varchar,
   parent_span_id varchar,
   start_time timestamp(9),
   duration_ns bigint,
   service_name varchar,
   span_name varchar,
   span_kind varchar,
   status_code varchar,
   http_status integer,
   db_system varchar
);

-- =============================================================================
-- Predictive Maintenance Tables
-- =============================================================================

-- Service baselines: stores computed statistical baselines per service/metric
CREATE TABLE vast."csnow-db|otel".service_baselines (
   computed_at timestamp(9),
   service_name varchar,
   metric_type varchar,           -- 'error_rate', 'latency_p50', 'latency_p95', 'latency_p99', 'throughput'
   baseline_mean double,
   baseline_stddev double,
   baseline_min double,
   baseline_max double,
   baseline_p50 double,
   baseline_p95 double,
   baseline_p99 double,
   sample_count bigint,
   window_hours integer           -- how many hours of data used to compute baseline
);

-- Anomaly scores: stores ML model predictions and anomaly detection results
CREATE TABLE vast."csnow-db|otel".anomaly_scores (
   timestamp timestamp(9),
   service_name varchar,
   metric_type varchar,
   current_value double,
   expected_value double,
   baseline_mean double,
   baseline_stddev double,
   z_score double,
   anomaly_score double,          -- 0.0 to 1.0, higher = more anomalous
   is_anomaly boolean,
   detection_method varchar       -- 'zscore', 'isolation_forest', 'trend', 'threshold'
);

-- Alerts: stores generated alerts with severity and status
-- Alert types include:
--   Symptom-based: 'error_spike', 'latency_degradation', 'throughput_drop', 'anomaly', 'trend', 'service_down'
--   Root cause: 'db_connection_failure', 'db_slow_queries', 'dependency_failure',
--               'dependency_latency', 'exception_surge', 'new_exception_type'
CREATE TABLE vast."csnow-db|otel".alerts (
   alert_id varchar,
   created_at timestamp(9),
   updated_at timestamp(9),
   service_name varchar,
   alert_type varchar,            -- See alert types above
   severity varchar,              -- 'info', 'warning', 'critical'
   title varchar,
   description varchar,
   metric_type varchar,
   current_value double,
   threshold_value double,
   baseline_value double,
   z_score double,
   status varchar,                -- 'active', 'acknowledged', 'resolved', 'archived'
   resolved_at timestamp(9),
   auto_resolved boolean
);

-- Alert investigations: LLM-powered root cause analysis
CREATE TABLE vast."csnow-db|otel".alert_investigations (
   investigation_id varchar,
   alert_id varchar,
   investigated_at timestamp(9),
   service_name varchar,
   alert_type varchar,
   model_used varchar,              -- 'claude-3-5-haiku-20241022'
   root_cause_summary varchar,
   recommended_actions varchar,
   supporting_evidence varchar,     -- JSON with relevant traces/errors found
   queries_executed integer,
   tokens_used integer
);

