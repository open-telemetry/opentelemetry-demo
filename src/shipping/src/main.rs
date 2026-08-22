// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{web, App, HttpResponse, HttpServer};
use open_feature::provider::{FeatureProvider, NoOpProvider};
use open_feature_flagd::{FlagdOptions, FlagdProvider};
use opentelemetry_instrumentation_actix_web::{RequestMetrics, RequestTracing};
use std::env;
use std::sync::Arc;
use tracing::{error, info};

mod telemetry_conf;
use telemetry_conf::init_otel;
mod shipping_service;
use shipping_service::{get_quote, ship_order};

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let otel_guard = match init_otel() {
        Ok(guard) => {
            info!("Successfully configured OTel");
            guard
        }
        Err(err) => {
            panic!("Couldn't start OTel: {0}", err);
        }
    };

    let port: u16 = env::var("SHIPPING_PORT")
        .expect("$SHIPPING_PORT is not set")
        .parse()
        .expect("$SHIPPING_PORT is not a valid port");

    let mut ip = "0.0.0.0".to_string();

    if let Ok(ipv6_enabled) = env::var("IPV6_ENABLED") {
        if ipv6_enabled == "true" {
            ip = "[::]".to_string();
            info!("Overwriting Localhost IP:  {ip}");
        }
    }

    let addr = format!("{}:{}", ip, port);
    info!(
        name: "shipping.server.started",
        addr = addr.as_str(),
        message = "Shipping service is running"
    );

    let flag_provider = match FlagdProvider::new(FlagdOptions {
        cache_settings: None,
        ..Default::default()
    })
    .await
    {
        Ok(provider) => web::Data::from(Arc::new(provider) as Arc<dyn FeatureProvider>),
        Err(err) => {
            error!(
                name: "shipping.flagd_provider.init_failed",
                error = ?err,
                "Failed to initialize flagd provider, falling back to NoOp provider"
            );
            web::Data::from(Arc::new(NoOpProvider::default()) as Arc<dyn FeatureProvider>)
        }
    };

    HttpServer::new(move || {
        App::new()
            .app_data(flag_provider.clone())
            .wrap(RequestTracing::new())
            .wrap(RequestMetrics::default())
            .service(get_quote)
            .service(ship_order)
            .route(
                "/health",
                web::get().to(|| async { HttpResponse::Ok().finish() }),
            )
    })
    .bind(&addr)?
    .run()
    .await?;

    otel_guard.shutdown();
    Ok(())
}
