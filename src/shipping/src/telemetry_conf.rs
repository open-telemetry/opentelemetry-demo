// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use anyhow::Result;
use opentelemetry::global;
use opentelemetry_appender_tracing::layer::OpenTelemetryTracingBridge;
use opentelemetry_sdk::logs::SdkLoggerProvider;
use opentelemetry_sdk::metrics::SdkMeterProvider;
use opentelemetry_sdk::trace::SdkTracerProvider;
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

fn init_tracer_provider() -> SdkTracerProvider {
    global::set_text_map_propagator(TraceContextPropagator::new());

    let tracer_provider = SdkTracerProvider::builder()
        .with_resource(get_resource())
        .with_batch_exporter(
            opentelemetry_otlp::SpanExporter::builder()
                .with_tonic()
                .build()
                .expect("Failed to initialize tracing provider"),
        )
        .build();

    global::set_tracer_provider(tracer_provider.clone());
    tracer_provider
}

fn init_meter_provider() -> SdkMeterProvider {
    let meter_provider = SdkMeterProvider::builder()
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

fn init_logger_provider() -> SdkLoggerProvider {
    let logger_provider = SdkLoggerProvider::builder()
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

    logger_provider
}

/// Holds all OTel provider handles for graceful shutdown.
pub struct OtelGuard {
    tracer_provider: SdkTracerProvider,
    logger_provider: SdkLoggerProvider,
    meter_provider: SdkMeterProvider,
}

impl OtelGuard {
    /// Shuts down all providers, flushing any buffered telemetry.
    /// Order: tracer → logger → meter (meter last because BatchLogProcessor
    /// may emit self-diagnostic metrics during its shutdown).
    pub fn shutdown(self) {
        if let Err(e) = self.tracer_provider.shutdown() {
            eprintln!("Failed to shutdown TracerProvider: {e}");
        }
        if let Err(e) = self.logger_provider.shutdown() {
            eprintln!("Failed to shutdown LoggerProvider: {e}");
        }
        if let Err(e) = self.meter_provider.shutdown() {
            eprintln!("Failed to shutdown MeterProvider: {e}");
        }
    }
}

pub fn init_otel() -> Result<OtelGuard> {
    let logger_provider = init_logger_provider();
    let tracer_provider = init_tracer_provider();
    let meter_provider = init_meter_provider();
    Ok(OtelGuard {
        tracer_provider,
        logger_provider,
        meter_provider,
    })
}
