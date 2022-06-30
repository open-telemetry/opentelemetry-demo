use opentelemetry::trace::TraceError;
use opentelemetry::{
    sdk::trace as sdktrace,
};
use opentelemetry_otlp::{self, WithExportConfig};

use tonic::{transport::Server};

use log::*;
use simplelog::*;

use std::env;

mod shipping_service;
use shipping_service::ShippingServer;
use shipping_service::shop::shipping_service_server::ShippingServiceServer;

mod health_service;
use health_service::HealthCheckServer;
use health_service::health::health_server::HealthServer;

fn init_logger() -> Result<(), log::SetLoggerError>{
    CombinedLogger::init(vec![
        SimpleLogger::new(LevelFilter::Info, Config::default()),
        SimpleLogger::new(LevelFilter::Warn, Config::default()),
        SimpleLogger::new(LevelFilter::Error, Config::default()),
    ])
    // debug is used on lower level apis and not used here.
}

fn init_tracer() -> Result<sdktrace::Tracer, TraceError> {
    opentelemetry_otlp::new_pipeline()
    .tracing()
    .with_exporter(
        opentelemetry_otlp::new_exporter()
            .tonic()    
            .with_endpoint("http://otelcol:4317/v1/traces")
            // TODO: assume this ^ is true from config when opentelemetry crate > v0.17.0
            // https://github.com/open-telemetry/opentelemetry-rust/pull/806 includes the environment variable.
    )
    .install_batch(opentelemetry::runtime::Tokio)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    init_logger()?;
    init_tracer()?;
    info!("OTel pipeline created");
    let port = env::var("PORT").unwrap_or_else( |_|{"50051".to_string()});
    let addr = format!("0.0.0.0:{}", port).parse()?;
    info!("listening on {}", addr);
    let shipper = ShippingServer::default();
    let health = HealthCheckServer::default();

    Server::builder()
        .add_service(ShippingServiceServer::new(shipper))
        .add_service(HealthServer::new(health))
        .serve(addr)
        .await?;
    
    Ok(())
}