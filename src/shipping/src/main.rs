// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{App, HttpServer};
use opentelemetry_instrumentation_actix_web::{RequestMetrics, RequestTracing};
use std::env;
use tracing::info;

mod telemetry_conf;
use telemetry_conf::init_otel;
mod shipping_service;
use shipping_service::{get_quote, ship_order};

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    match init_otel() {
        Ok(_) => {
            info!("Successfully configured OTel");
        }
        Err(err) => {
            panic!("Couldn't start OTel: {0}", err);
        }
    };

    let port: u16 = env::var("SHIPPING_PORT")
        .expect("$SHIPPING_PORT is not set")
        .parse()
        .expect("$SHIPPING_PORT is not a valid port");
    
    let ipv6_enabled = env::var("IPV6_ENABLED")
        .unwrap_or_default()
        .to_lowercase() == "true" || env::var("IPV6_ENABLED").unwrap_or_default() == "1";
    
    let addr = if ipv6_enabled {
        format!("[::]:{}", port)  // IPv6 all interfaces
    } else {
        format!("0.0.0.0:{}", port)  // IPv4 all interfaces
    };
    
    println!("DEBUG: IPV6_ENABLED = {}", env::var("IPV6_ENABLED").unwrap_or_default());
    println!("DEBUG: Binding to {} (IPv6 {})", addr, if ipv6_enabled { "ENABLED" } else { "DISABLED" });
    info!(
        name = "ServerStartedSuccessfully",
        addr = addr.as_str(),
        message = "Shipping service is running"
    );

    HttpServer::new(|| {
        App::new()
            .wrap(RequestTracing::new())
            .wrap(RequestMetrics::default())
            .service(get_quote)
            .service(ship_order)
    })
    .bind(&addr)?
    .run()
    .await
}
