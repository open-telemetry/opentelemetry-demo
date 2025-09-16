// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{post, web, HttpResponse, Responder};
use tracing::info;

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

mod shipping_types;
pub use shipping_types::*;

const NANOS_MULTIPLE: u32 = 10000000u32;

#[post("/get-quote")]
pub async fn get_quote(req: web::Json<GetQuoteRequest>) -> impl Responder {
    // stdout debugging
    println!("[shipping][get-quote] received request with {} item(s)", req.items.len());
    if !req.items.is_empty() {
        println!(
            "[shipping][get-quote] first item: quantity={}",
            req.items[0].quantity
        );
    }
    let itemct: u32 = req.items.iter().map(|item| item.quantity as u32).sum();
    println!("[shipping][get-quote] total_item_count={}", itemct);

    let quote = match create_quote_from_count(itemct).await {
        Ok(q) => {
            println!(
                "[shipping][get-quote] quote calculation succeeded: dollars={}, cents={}",
                q.dollars, q.cents
            );
            q
        },
        Err(e) => {
            println!("[shipping][get-quote][ERROR] failed to get quote: {}", e);
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

    println!(
        "[shipping][get-quote] replying 200 with cost: currency=USD, units={}, nanos={}",
        quote.dollars,
        quote.cents * NANOS_MULTIPLE
    );

    info!(
        name = "SendingQuoteValue",
        quote.dollars = quote.dollars,
        quote.cents = quote.cents,
        message = "Sending Quote"
    );

    HttpResponse::Ok().json(reply)
}

#[post("/ship-order")]
pub async fn ship_order(_req: web::Json<ShipOrderRequest>) -> impl Responder {
    // stdout debugging
    println!("[shipping][ship-order] received request");
    let tid = create_tracking_id();
    println!("[shipping][ship-order] generated tracking_id={}", tid);
    info!(
        name = "CreatingTrackingId",
        tracking_id = tid.as_str(),
        message = "Tracking ID Created"
    );
    println!("[shipping][ship-order] replying 200 with tracking_id={}", tid);
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
