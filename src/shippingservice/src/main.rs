// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use opentelemetry::global;
use opentelemetry::trace::TraceError;
use opentelemetry_otlp;
use opentelemetry_sdk::{
    propagation::TraceContextPropagator,
    resource::{
        EnvResourceDetector, OsResourceDetector, ProcessResourceDetector, ResourceDetector,
        SdkProvidedResourceDetector, TelemetryResourceDetector,
    },
    runtime, trace as sdktrace,
};

use tonic::transport::Server;

use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::Registry;

use log::*;
use simplelog::*;

use std::env;
use std::time::Duration;

mod shipping_service;
use shipping_service::shop::shipping_service_server::ShippingServiceServer;
use shipping_service::ShippingServer;

fn init_logger() -> Result<(), log::SetLoggerError> {
    CombinedLogger::init(vec![
        SimpleLogger::new(LevelFilter::Info, Config::default()),
        SimpleLogger::new(LevelFilter::Warn, Config::default()),
        SimpleLogger::new(LevelFilter::Error, Config::default()),
    ])
    // debug is used on lower level apis and not used here.
}

fn init_tracer() -> Result<sdktrace::Tracer, TraceError> {
    global::set_text_map_propagator(TraceContextPropagator::new());
    let os_resource = OsResourceDetector.detect(Duration::from_secs(0));
    let process_resource = ProcessResourceDetector.detect(Duration::from_secs(0));
    let sdk_resource = SdkProvidedResourceDetector.detect(Duration::from_secs(0));
    let env_resource = EnvResourceDetector::new().detect(Duration::from_secs(0));
    let telemetry_resource = TelemetryResourceDetector.detect(Duration::from_secs(0));
    opentelemetry_otlp::new_pipeline()
        .tracing()
        .with_exporter(opentelemetry_otlp::new_exporter().tonic())
        .with_trace_config(
            sdktrace::config().with_resource(
                os_resource
                    .merge(&process_resource)
                    .merge(&sdk_resource)
                    .merge(&env_resource)
                    .merge(&telemetry_resource),
            ),
        )
        .install_batch(runtime::Tokio)
}

fn init_reqwest_tracing(
    tracer: sdktrace::Tracer,
) -> Result<(), tracing::subscriber::SetGlobalDefaultError> {
    let telemetry = tracing_opentelemetry::layer().with_tracer(tracer);
    let subscriber = Registry::default().with(telemetry);
    tracing::subscriber::set_global_default(subscriber)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (mut health_reporter, health_service) = tonic_health::server::health_reporter();
    health_reporter
        .set_serving::<ShippingServiceServer<ShippingServer>>()
        .await;

    init_logger()?;
    init_reqwest_tracing(init_tracer()?)?;
    info!("OTel pipeline created");
    let port = env::var("SHIPPING_SERVICE_PORT").expect("$SHIPPING_SERVICE_PORT is not set");
    let addr = format!("0.0.0.0:{}", port).parse()?;
    info!("listening on {}", addr);
    let shipper = ShippingServer::default();

    Server::builder()
        .add_service(ShippingServiceServer::new(shipper))
        .add_service(health_service)
        .serve(addr)
        .await?;

    Ok(())
}
