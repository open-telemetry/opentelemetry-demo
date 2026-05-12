// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{post, web, HttpResponse, Responder};
use serde::de::DeserializeOwned;
use std::any::Any;
use tracing::info;

mod feature_flag;
use feature_flag::FlagdClient;

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

mod shipping_types;
pub use shipping_types::*;

pub enum FlagChecker {
    Real(FlagdClient),
    #[cfg(test)]
    Mock(std::collections::HashMap<String, Box<dyn Any + Send + Sync>>),
}

impl FlagChecker {
    pub fn from_env() -> Self {
        Self::Real(FlagdClient::from_env())
    }

    pub async fn evaluate<T: DeserializeOwned + Default + Clone + Any + Send + 'static>(
        &self,
        flag_name: &str,
    ) -> T {
        match self {
            Self::Real(client) => client.evaluate(flag_name).await,
            #[cfg(test)]
            Self::Mock(flags) => flags
                .get(flag_name)
                .and_then(|v| v.downcast_ref::<T>())
                .cloned()
                .unwrap_or_default(),
        }
    }
}

const NANOS_MULTIPLE: u32 = 10000000u32;
pub const DEFAULT_SLOWDOWN: std::time::Duration = std::time::Duration::from_secs(10);

#[post("/get-quote")]
pub async fn get_quote(req: web::Json<GetQuoteRequest>) -> impl Responder {
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
        message = "Sending Quote"
    );

    HttpResponse::Ok().json(reply)
}

#[post("/ship-order")]
pub async fn ship_order(
    req: web::Json<ShipOrderRequest>,
    flag_checker: web::Data<FlagChecker>,
    slowdown: web::Data<std::time::Duration>,
) -> impl Responder {
    let is_outside_us = req
        .address
        .as_ref()
        .map(|addr| {
            !matches!(
                addr.country.to_uppercase().trim(),
                "US" | "USA" | "UNITED STATES" | "UNITED STATES OF AMERICA"
            )
        })
        .unwrap_or(false);

    if is_outside_us && flag_checker.evaluate::<bool>("shippingSlowdown").await {
        info!(
            name = "ShippingSlowdown",
            message = "Delaying international shipment due to shippingSlowdown feature flag"
        );
        actix_web::rt::time::sleep(**slowdown).await;
    }

    let tid = create_tracking_id();
    info!(
        name = "CreatingTrackingId",
        tracking_id = tid.as_str(),
        message = "Tracking ID Created"
    );
    HttpResponse::Ok().json(ShipOrderResponse { tracking_id: tid })
}

#[cfg(test)]
mod tests {
    use actix_web::{http::header::ContentType, test, App};

    use super::*;

    fn mock_checker() -> FlagChecker {
        FlagChecker::Mock(std::collections::HashMap::new())
    }

    fn mock_checker_with(flag: &str, value: impl Any + Send + Sync + 'static) -> FlagChecker {
        let mut map = std::collections::HashMap::new();
        map.insert(flag.to_string(), Box::new(value) as Box<dyn Any + Send + Sync>);
        FlagChecker::Mock(map)
    }

    async fn call_ship_order(
        address: Option<Address>,
        checker: FlagChecker,
        slowdown: std::time::Duration,
    ) -> ShipOrderResponse {
        let checker = web::Data::new(checker);
        let app = test::init_service(
            App::new()
                .app_data(checker)
                .app_data(web::Data::new(slowdown))
                .service(ship_order),
        )
        .await;
        let req = test::TestRequest::post()
            .uri("/ship-order")
            .insert_header(ContentType::json())
            .set_json(&ShipOrderRequest { address, items: vec![] })
            .to_request();
        let resp = test::call_service(&app, req).await;
        assert!(resp.status().is_success());
        test::read_body_json(resp).await
    }

    fn make_address(country: &str) -> Address {
        Address {
            street_address: "123 Main St".into(),
            city: "Anytown".into(),
            state: "CA".into(),
            country: country.into(),
            zip_code: "00000".into(),
        }
    }

    #[actix_web::test]
    async fn test_ship_order_no_address() {
        let order = call_ship_order(None, mock_checker(), std::time::Duration::ZERO).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_us_address() {
        let order = call_ship_order(Some(make_address("US")), mock_checker(), std::time::Duration::ZERO).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_international_flag_off() {
        let order = call_ship_order(Some(make_address("CA")), mock_checker(), std::time::Duration::ZERO).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_international_flag_on() {
        let slowdown = std::time::Duration::from_millis(50);
        let start = std::time::Instant::now();
        let checker = mock_checker_with("shippingSlowdown", true);
        let order = call_ship_order(Some(make_address("CA")), checker, slowdown).await;
        assert!(start.elapsed() >= slowdown);
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_us_flag_on() {
        let slowdown = std::time::Duration::from_millis(50);
        let checker = mock_checker_with("shippingSlowdown", true);
        let start = std::time::Instant::now();
        let order = call_ship_order(Some(make_address("US")), checker, slowdown).await;
        assert!(start.elapsed() < slowdown);
        assert!(!order.tracking_id.is_empty());
    }
}
