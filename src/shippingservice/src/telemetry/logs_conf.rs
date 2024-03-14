// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use opentelemetry_appender_tracing::layer::OpenTelemetryTracingBridge;
use opentelemetry_sdk::{logs::Config, runtime};

use tracing_subscriber::prelude::*;

use opentelemetry_sdk::logs as sdklogs;

use super::get_resource_attr;

pub fn init_logger() -> Result<sdklogs::Logger, opentelemetry::logs::LogError> {
    opentelemetry_otlp::new_pipeline()
        .logging()
        .with_log_config(Config::default().with_resource(get_resource_attr()))
        .with_exporter(opentelemetry_otlp::new_exporter().tonic())
        .install_batch(runtime::Tokio)
}

pub fn configure_global_logger(tracer: opentelemetry_sdk::trace::Tracer) {
    let telemetry = tracing_opentelemetry::layer().with_tracer(tracer);
    let logger_provider = opentelemetry::global::logger_provider();
    let layer = OpenTelemetryTracingBridge::new(&logger_provider);
    let _ = tracing_subscriber::registry()
        .with(layer)
        .with(telemetry)
        .init();
}
