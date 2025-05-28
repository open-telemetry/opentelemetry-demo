// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{App, HttpServer};
use actix_web_opentelemetry::RequestTracing;
use log::{info, warn};
use std::env;

mod telemetry_conf;
use telemetry_conf::init_otel;
mod shipping_service;
use shipping_service::{get_quote, ship_order};
mod health_check;
use health_check::health;

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    match init_otel() {
        Ok(_) => {
            info!("Successfully configured OTel");
        }
        Err(err) => {
            warn!(
                "Couldn't start OTel! Starting without telemetry: {0}",
                err
            );
        }
    };

    let port = env::var("SHIPPING_PORT").expect("$SHIPPING_PORT is not set");
    let addr = format!("0.0.0.0:{}", port);
    info!("listening on {}", addr);

    HttpServer::new(|| {
        App::new()
            .wrap(RequestTracing::new())
            .service(get_quote)
            .service(health)
            .service(ship_order)
    })
    .bind(&addr)?
    .run()
    .await
}
