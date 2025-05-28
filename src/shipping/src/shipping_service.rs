// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{post, web, Responder, HttpResponse};
use log::*;

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

mod shipping_types;
pub use shipping_types::*;

const NANOS_MULTIPLE: i32 = 10000000i32;

#[post("/get-quote")]
pub async fn get_quote(req: web::Json<GetQuoteRequest>) -> impl Responder {
    let itemct: u32 = req.items.iter().map(|item| item.quantity as u32).sum();

    let quote = match create_quote_from_count(itemct).await {
        Ok(q) => q,
        Err(_) => return HttpResponse::InternalServerError().finish(),
    };

    let reply = GetQuoteResponse {
        cost_usd: Some(Money {
            currency_code: "USD".into(),
            units: quote.dollars,
            nanos: quote.cents * NANOS_MULTIPLE,
        }),
    };
    info!("Sending Quote: {:?}", quote);
    HttpResponse::Ok().json(reply)
}

#[post("/ship-order")]
pub async fn ship_order(_req: web::Json<ShipOrderRequest>) -> impl Responder {
    let tid = create_tracking_id();
    info!("Tracking ID Created: {}", tid);
    HttpResponse::Ok().json(ShipOrderResponse { tracking_id: tid })
}
