// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{post, web, HttpResponse, Responder};
use std::{future::Future, pin::Pin, sync::Arc};
use tracing::info;

mod feature_flag;

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

mod shipping_types;
pub use shipping_types::*;

pub type FlagChecker =
    Arc<dyn Fn(String) -> Pin<Box<dyn Future<Output = bool>>> + Send + Sync>;

pub fn default_flag_checker() -> FlagChecker {
    Arc::new(|flag: String| {
        Box::pin(async move { feature_flag::is_feature_flag_enabled(&flag).await })
    })
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
        .map(|addr| addr.country.to_uppercase() != "US")
        .unwrap_or(false);

    if is_outside_us && flag_checker("shippingSlowdown".to_string()).await {
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

    struct MockFlagChecker {
        flags: std::collections::HashMap<&'static str, bool>,
    }

    impl MockFlagChecker {
        fn new() -> Self {
            Self { flags: std::collections::HashMap::new() }
        }

        fn with_flag(mut self, flag: &'static str, enabled: bool) -> Self {
            self.flags.insert(flag, enabled);
            self
        }

        fn build(self) -> web::Data<FlagChecker> {
            let map = self.flags;
            web::Data::new(Arc::new(move |flag: String| {
                let value = map.get(flag.as_str()).copied().unwrap_or(false);
                Box::pin(async move { value }) as Pin<Box<dyn Future<Output = bool>>>
            }) as FlagChecker)
        }
    }

    async fn call_ship_order(
        address: Option<Address>,
        checker: web::Data<FlagChecker>,
        slowdown: std::time::Duration,
    ) -> ShipOrderResponse {
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
        let order = call_ship_order(None, MockFlagChecker::new().build(), std::time::Duration::ZERO).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_us_address() {
        let order = call_ship_order(Some(make_address("US")), MockFlagChecker::new().build(), std::time::Duration::ZERO).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_international_flag_off() {
        let order = call_ship_order(Some(make_address("CA")), MockFlagChecker::new().build(), std::time::Duration::ZERO).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_international_flag_on() {
        let slowdown = std::time::Duration::from_millis(50);
        let start = std::time::Instant::now();
        let checker = MockFlagChecker::new().with_flag("shippingSlowdown", true).build();
        let order = call_ship_order(Some(make_address("CA")), checker, slowdown).await;
        assert!(start.elapsed() >= slowdown);
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_us_flag_on() {
        // US addresses must not be delayed even when the flag is on
        let slowdown = std::time::Duration::from_millis(50);
        let start = std::time::Instant::now();
        let checker = MockFlagChecker::new().with_flag("shippingSlowdown", true).build();
        let order = call_ship_order(Some(make_address("US")), checker, slowdown).await;
        assert!(start.elapsed() < slowdown);
        assert!(!order.tracking_id.is_empty());
    }
}
