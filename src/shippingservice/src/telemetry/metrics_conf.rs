// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use opentelemetry::metrics::MetricsError;
use opentelemetry_sdk::{metrics::MeterProvider, runtime};

use super::get_resource_attr;

pub fn init_metrics() -> Result<MeterProvider, MetricsError> {
    opentelemetry_otlp::new_pipeline()
        .metrics(runtime::Tokio)
        .with_exporter(opentelemetry_otlp::new_exporter().tonic())
        .with_resource(get_resource_attr())
        .build()
}
