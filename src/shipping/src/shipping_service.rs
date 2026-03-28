// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{post, web, HttpResponse, Responder};
use opentelemetry::{global, KeyValue};
use opentelemetry::metrics::Histogram;
use std::sync::OnceLock;
use std::time::Instant;
use tracing::info;

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

mod shipping_types;
pub use shipping_types::*;

const NANOS_MULTIPLE: u32 = 10000000u32;

// CUP-3 latency histograms — initialised once, reused across requests.
static QUOTE_DURATION: OnceLock<Histogram<f64>> = OnceLock::new();
static SHIP_DURATION: OnceLock<Histogram<f64>> = OnceLock::new();

fn quote_duration_histogram() -> &'static Histogram<f64> {
    QUOTE_DURATION.get_or_init(|| {
        global::meter("shipping")
            .f64_histogram("app.shipping.quote.duration")
            .with_description("Duration of the get-quote handler in milliseconds")
            .with_unit("ms")
            .build()
    })
}

fn ship_duration_histogram() -> &'static Histogram<f64> {
    SHIP_DURATION.get_or_init(|| {
        global::meter("shipping")
            .f64_histogram("app.shipping.ship.duration")
            .with_description("Duration of the ship-order handler in milliseconds")
            .with_unit("ms")
            .build()
    })
}

#[post("/get-quote")]
pub async fn get_quote(req: web::Json<GetQuoteRequest>) -> impl Responder {
    let start = Instant::now();
    let itemct: u32 = req.items.iter().map(|item| item.quantity as u32).sum();

    let quote = match create_quote_from_count(itemct).await {
        Ok(q) => q,
        Err(e) => {
            return HttpResponse::InternalServerError().body(format!("Failed to get quote: {}", e));
        }
    };

    let reply = GetQuoteResponse {
        cost_usd: Some(Money {
            currency_code: "USD".into(),
            units: quote.dollars,
            nanos: quote.cents * NANOS_MULTIPLE,
        }),
    };

    info!(
        name = "SendingQuoteValue",
        quote.dollars = quote.dollars,
        quote.cents = quote.cents,
        app.shipping.items.count = itemct,
        app.shipping.quote.usd = format!("{}.{}", quote.dollars, quote.cents),
        message = "Sending Quote"
    );

    // Record latency and item count for SLO measurement
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    quote_duration_histogram().record(elapsed_ms, &[
        KeyValue::new("app.shipping.items.count", itemct as i64),
    ]);

    HttpResponse::Ok().json(reply)
}

#[post("/ship-order")]
pub async fn ship_order(_req: web::Json<ShipOrderRequest>) -> impl Responder {
    let start = Instant::now();
    let tid = create_tracking_id();
    info!(
        name = "CreatingTrackingId",
        tracking_id = tid.as_str(),
        message = "Tracking ID Created"
    );

    // Record ship-order latency for SLO measurement
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    ship_duration_histogram().record(elapsed_ms, &[]);

    HttpResponse::Ok().json(ShipOrderResponse { tracking_id: tid })
}

#[cfg(test)]
mod tests {
    use actix_web::{http::header::ContentType, test, App};

    use super::*;

    #[actix_web::test]
    async fn test_ship_order() {
        let app = test::init_service(App::new().service(ship_order)).await;
        let req = test::TestRequest::post()
            .uri("/ship-order")
            .insert_header(ContentType::json())
            .set_json(&ShipOrderRequest {})
            .to_request();
        let resp = test::call_service(&app, req).await;
        assert!(resp.status().is_success());

        let order: ShipOrderResponse = test::read_body_json(resp).await;
        assert!(!order.tracking_id.is_empty());
    }
}
