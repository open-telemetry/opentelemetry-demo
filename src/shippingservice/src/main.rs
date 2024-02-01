// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use opentelemetry::trace::TraceError;
use opentelemetry::global;
use opentelemetry_sdk::{propagation::TraceContextPropagator, resource::{
    OsResourceDetector, ProcessResourceDetector, ResourceDetector,
    EnvResourceDetector, TelemetryResourceDetector,
    SdkProvidedResourceDetector,
}, runtime, trace as sdktrace};
use opentelemetry_otlp::{self, WithExportConfig};

use tonic::transport::{Channel, Server};

use tracing_subscriber::Registry;
use tracing_subscriber::layer::SubscriberExt;

use log::*;
use simplelog::*;

use std::env;
use std::time::Duration;

mod shipping_service;

use shipping_service::shop::shipping_service_server::ShippingServiceServer;
use shipping_service::ShippingServer;
use shop::feature_flag_service_client::FeatureFlagServiceClient;

pub mod shop {
    // The string specified here must match the proto package name
    tonic::include_proto!("oteldemo");
}

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
        .with_exporter(
            opentelemetry_otlp::new_exporter()
                .tonic()
                .with_endpoint(format!(
                    "{}{}",
                    env::var("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
                        .unwrap_or_else(|_| "http://otelcol:4317".to_string()),
                    "/v1/traces"
                )), // TODO: assume this ^ is true from config when opentelemetry crate > v0.17.0
                    // https://github.com/open-telemetry/opentelemetry-rust/pull/806 includes the environment variable.
        )
        .with_trace_config(
            sdktrace::config()
                .with_resource(os_resource.merge(&process_resource).merge(&sdk_resource).merge(&env_resource).merge(&telemetry_resource)),
        )
        .install_batch(runtime::Tokio)
}

fn init_reqwest_tracing(tracer: sdktrace::Tracer) -> Result<(), tracing::subscriber::SetGlobalDefaultError> {
    let telemetry = tracing_opentelemetry::layer().with_tracer(tracer);
    let subscriber = Registry::default().with(telemetry);
    tracing::subscriber::set_global_default(subscriber)
}

async fn init_feature_flag_client() -> Option<FeatureFlagServiceClient<Channel>> {
    let ffs_addr_env = env::var("FEATURE_FLAG_GRPC_SERVICE_ADDR");
    if ffs_addr_env.is_ok() {
        let addr = ffs_addr_env.unwrap();
        let addr_with_scheme = "http://".to_owned() + addr.as_str();
        info!("Trying to connect to feature flag service at: {}", addr_with_scheme);
        let result = Channel::from_shared(addr_with_scheme.clone());
        if result.is_ok() {
            let ffs_channel = result.ok()?.connect().await;
            if ffs_channel.is_ok() {
                let ffc = FeatureFlagServiceClient::new(ffs_channel.ok()?);
                info!("Connected to feature flag service at: {}", addr_with_scheme);
                return Some(ffc);
            }
            warn!("Could not connect to feature flag service at: {}, simulated slowness will not be enabled.", addr_with_scheme);
        }
    } else {
        warn!("FEATURE_FLAG_GRPC_SERVICE_ADDR is not set, simulated slowness will not be enabled.");
    }
    return None
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (mut health_reporter, health_service) = tonic_health::server::health_reporter();
    health_reporter
        .set_serving::<ShippingServiceServer<ShippingServer>>()
        .await;

    init_logger()?;
    init_reqwest_tracing(init_tracer()?)?;
    let feature_flag_client = init_feature_flag_client().await;

    info!("OTel pipeline created");
    let port = env::var("SHIPPING_SERVICE_PORT").expect("$SHIPPING_SERVICE_PORT is not set");
    let addr = format!("0.0.0.0:{}", port).parse()?;
    info!("listening on {}", addr);
    let shipper = ShippingServer::new(feature_flag_client);

    Server::builder()
        .add_service(ShippingServiceServer::new(shipper))
        .add_service(health_service)
        .serve(addr)
        .await?;

    Ok(())
}