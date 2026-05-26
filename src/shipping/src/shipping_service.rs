// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{post, web, HttpResponse, Responder};
use open_feature::provider::FeatureProvider;
use open_feature::EvaluationContext;
use tracing::{info, warn};

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

mod shipping_types;
pub use shipping_types::*;

const NANOS_MULTIPLE: u32 = 10000000u32;

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
    flag_provider: web::Data<dyn FeatureProvider>,
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

    let slowdown_secs = if is_outside_us {
        flag_provider
            .resolve_int_value("intlShippingSlowdown", &EvaluationContext::default())
            .await
            .map(|res| {
                info!(
                    feature_flag.key = "intlShippingSlowdown",
                    feature_flag.provider_name = "flagd",
                    feature_flag.variant = res.variant.as_deref().unwrap_or("unknown"),
                    message = "feature flag evaluated"
                );
                res.value
            })
            .unwrap_or_else(|e| {
                warn!("Failed to evaluate feature flag intlShippingSlowdown: {:?}", e);
                0
            })
    } else {
        0
    };

    if slowdown_secs > 0 {
        info!(
            name = "IntlShippingSlowdown",
            shipping.delay_secs = slowdown_secs,
            message = "Delaying international shipment due to intlShippingSlowdown feature flag"
        );
        actix_web::rt::time::sleep(std::time::Duration::from_secs(slowdown_secs as u64)).await;
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
    use open_feature::provider::{MockFeatureProvider, ResolutionDetails};
    use std::sync::Arc;

    use super::*;

    fn mock_provider(value: i64) -> web::Data<dyn FeatureProvider> {
        let mut mock = MockFeatureProvider::new();
        mock.expect_resolve_int_value()
            .returning(move |_, _| Ok(ResolutionDetails::new(value)));
        web::Data::from(Arc::new(mock) as Arc<dyn FeatureProvider>)
    }

    async fn call_ship_order(
        address: Option<Address>,
        provider: web::Data<dyn FeatureProvider>,
    ) -> ShipOrderResponse {
        let app = test::init_service(
            App::new()
                .app_data(provider)
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
        let order = call_ship_order(None, mock_provider(0)).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_us_address() {
        let order = call_ship_order(Some(make_address("US")), mock_provider(0)).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_international_flag_off() {
        let order = call_ship_order(Some(make_address("FR")), mock_provider(0)).await;
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_international_flag_on() {
        let start = std::time::Instant::now();
        let order = call_ship_order(Some(make_address("FR")), mock_provider(1)).await;
        assert!(start.elapsed() >= std::time::Duration::from_secs(1));
        assert!(!order.tracking_id.is_empty());
    }

    #[actix_web::test]
    async fn test_ship_order_us_flag_on() {
        let start = std::time::Instant::now();
        let order = call_ship_order(Some(make_address("US")), mock_provider(10)).await;
        assert!(start.elapsed() < std::time::Duration::from_secs(1));
        assert!(!order.tracking_id.is_empty());
    }
}
