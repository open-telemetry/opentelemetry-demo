// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use opentelemetry::{global, trace::TraceError};
use opentelemetry_otlp;
use opentelemetry_sdk::{propagation::TraceContextPropagator, runtime, trace as sdktrace};

use super::get_resource_attr;

pub fn init_tracer() -> Result<sdktrace::Tracer, TraceError> {
    global::set_text_map_propagator(TraceContextPropagator::new());

    opentelemetry_otlp::new_pipeline()
        .tracing()
        .with_exporter(opentelemetry_otlp::new_exporter().tonic())
        .with_trace_config(sdktrace::config().with_resource(get_resource_attr()))
        .install_batch(runtime::Tokio)
}
