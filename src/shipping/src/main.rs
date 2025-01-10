// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use tonic::transport::Server;

use log::*;

use std::env;

mod shipping_service;
use shipping_service::shop::shipping_service_server::ShippingServiceServer;
use shipping_service::ShippingServer;

mod telemetry;
use telemetry::init_logger;

use telemetry::init_reqwest_tracing;
use telemetry::init_tracer;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (mut health_reporter, health_service) = tonic_health::server::health_reporter();
    health_reporter
        .set_serving::<ShippingServiceServer<ShippingServer>>()
        .await;

    init_logger()?;
    init_reqwest_tracing(init_tracer()?)?;

    info!("OTel pipeline created");
    let port = env::var("SHIPPING_PORT").expect("$SHIPPING_PORT is not set");
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
