// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use log::Level;
use opentelemetry::global::logger_provider;
use opentelemetry_appender_log::OpenTelemetryLogBridge;

use opentelemetry_otlp;
use opentelemetry_sdk::{logs::Config, runtime};

use super::get_resource_attr;

pub fn init_logger() {
    let _ = opentelemetry_otlp::new_pipeline()
        .logging()
        .with_log_config(Config::default().with_resource(get_resource_attr()))
        .with_exporter(opentelemetry_otlp::new_exporter().tonic())
        .install_batch(runtime::Tokio);

    set_log_bridge();
}

fn set_log_bridge() {
    let logger_provider = logger_provider();

    let otel_log_appender = OpenTelemetryLogBridge::new(&logger_provider);
    log::set_boxed_logger(Box::new(otel_log_appender)).unwrap();
    log::set_max_level(Level::Info.to_level_filter());
}
