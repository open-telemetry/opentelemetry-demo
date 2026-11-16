// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use anyhow::Result;
use opentelemetry::global;
use opentelemetry_appender_tracing::layer::OpenTelemetryTracingBridge;
use tracing_subscriber::prelude::*;
use tracing_subscriber::EnvFilter;

use opentelemetry_resource_detectors::{OsResourceDetector, ProcessResourceDetector};
use opentelemetry_sdk::{
    propagation::TraceContextPropagator, resource::ResourceDetector, Resource,
};

fn get_resource() -> Resource {
    let detectors: Vec<Box<dyn ResourceDetector>> = vec![
        Box::new(OsResourceDetector),
        Box::new(ProcessResourceDetector),
    ];

    Resource::builder().with_detectors(&detectors).build()
}

fn init_tracer_provider() {
    global::set_text_map_propagator(TraceContextPropagator::new());

    let tracer_provider = opentelemetry_sdk::trace::SdkTracerProvider::builder()
        .with_resource(get_resource())
        .with_batch_exporter(
            opentelemetry_otlp::SpanExporter::builder()
                .with_tonic()
                .build()
                .expect("Failed to initialize tracing provider"),
        )
        .build();

    global::set_tracer_provider(tracer_provider);
}

fn init_meter_provider() -> opentelemetry_sdk::metrics::SdkMeterProvider {
    let meter_provider = opentelemetry_sdk::metrics::SdkMeterProvider::builder()
        .with_resource(get_resource())
        .with_periodic_exporter(
            opentelemetry_otlp::MetricExporter::builder()
                .with_tonic()
                .build()
                .expect("Failed to initialize metric exporter"),
        )
        .build();
    global::set_meter_provider(meter_provider.clone());

    meter_provider
}

fn init_logger_provider() {
    let logger_provider = opentelemetry_sdk::logs::SdkLoggerProvider::builder()
        .with_resource(get_resource())
        .with_batch_exporter(
            opentelemetry_otlp::LogExporter::builder()
                .with_tonic()
                .build()
                .expect("Failed to initialize logger provider"),
        )
        .build();

    let otel_layer = OpenTelemetryTracingBridge::new(&logger_provider);
    let filter_otel = EnvFilter::new("info");
    let otel_layer = otel_layer.with_filter(filter_otel);

    tracing_subscriber::registry().with(otel_layer).init();
}

pub fn init_otel() -> Result<()> {
    init_logger_provider();
    init_tracer_provider();
    init_meter_provider();
    init_pyroscope().ok(); // profiling is best-effort; never block startup
    Ok(())
}

// Continuous profiling: the pyroscope agent pushes pprof samples to the estate
// Pyroscope when PYROSCOPE_SERVER_ADDRESS is set (deploy/telemetry-env-patches.yaml).
// No span_id labelling in the Rust agent (pyroscope-rs), so profiles are keyed by
// application name/tags only.
fn init_pyroscope() -> Result<(), Box<dyn std::error::Error>> {
    let addr = match std::env::var("PYROSCOPE_SERVER_ADDRESS") {
        Ok(v) if !v.is_empty() => v,
        _ => return Ok(()), // profiling off; local/estate-less runs unchanged
    };
    let app_name = std::env::var("OTEL_SERVICE_NAME")
        .ok()
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| "shipping".to_string());

    let agent = pyroscope::pyroscope::PyroscopeAgentBuilder::new(
        addr,
        app_name,
        100,
        "pyroscope-rs",
        env!("CARGO_PKG_VERSION"),
        pyroscope::backend::pprof_backend(
            pyroscope::backend::PprofConfig::default(),
            pyroscope::backend::BackendConfig::default(),
        ),
    )
    .basic_auth(
        std::env::var("PYROSCOPE_BASIC_AUTH_USER").unwrap_or_default(),
        std::env::var("PYROSCOPE_BASIC_AUTH_PASSWORD").unwrap_or_default(),
    )
    .tags(vec![("service_namespace", "opentelemetry-demo")])
    .build()?;

    // agent running state must be kept alive for the process lifetime
    std::mem::forget(agent.start()?);
    Ok(())
}
