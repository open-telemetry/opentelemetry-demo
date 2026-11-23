// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{post, web, HttpResponse, Responder};
use open_feature::provider::FeatureProvider;
use open_feature::EvaluationContext;
use tracing::{error, event, info, warn, Level};

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

mod shipping_types;
pub use shipping_types::*;

const NANOS_MULTIPLE: u32 = 10000000u32;
const MAX_SLOWDOWN_SECS: i64 = 10;

fn destination_country(address: Option<&Address>) -> String {
    address
        .map(|address| address.country.trim())
        .filter(|country| !country.is_empty())
        .map(str::to_uppercase)
        .unwrap_or_else(|| "unknown".to_string())
}

#[post("/get-quote")]
pub async fn get_quote(req: web::Json<GetQuoteRequest>) -> impl Responder {
    let start = std::time::Instant::now();
    let itemct: u32 = req.items.iter().map(|item| item.quantity as u32).sum();

    let quote = match create_quote_from_count(itemct).await {
        Ok(q) => q,
        Err(e) => {
            error!(name: "shipping.quote.failed", error = %e, "Failed to get quote: {}", e);
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

    let country = destination_country(req.address.as_ref());
    let quote_amount = quote.dollars as f64 + quote.cents as f64 / 100.0;
    event!(
        name: "shipping.quote.sent",
        Level::INFO,
        demo.shipping.quote.items_count = itemct,
        demo.shipping.quote.cost.total = quote_amount,
        demo.shipping.destination.country = country.as_str(),
        "Shipping quote returned: {} items to {}, ${:.2} in {} ms",
        itemct,
        country,
        quote_amount,
        start.elapsed().as_millis()
    );

    HttpResponse::Ok().json(reply)
}

#[post("/ship-order")]
pub async fn ship_order(
    req: web::Json<ShipOrderRequest>,
    flag_provider: web::Data<dyn FeatureProvider>,
) -> impl Responder {
    let start = std::time::Instant::now();
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
                    name: "shipping.feature_flag.evaluated",
                    feature_flag_key = "intlShippingSlowdown",
                    feature_flag_provider_name = "flagd",
                    feature_flag_variant = res.variant.as_deref().unwrap_or("unknown"),
                );
                res.value
            })
            .unwrap_or_else(|e| {
                warn!(name: "shipping.feature_flag.evaluation_failed", error = ?e);
                0
            })
    } else {
        0
    };

    if !(0..=MAX_SLOWDOWN_SECS).contains(&slowdown_secs) {
        error!(
            name: "shipping.international.invalid_slowdown",
            slowdown_secs,
            "Invalid international shipping slowdown; skipping delay"
        );
    } else if slowdown_secs > 0 {
        event!(
            name: "shipping.international.slowdown",
            Level::WARN,
            demo.shipping.delay_ms = slowdown_secs * 1000,
            "International shipment delayed"
        );
        actix_web::rt::time::sleep(std::time::Duration::from_secs(slowdown_secs as u64)).await;
    }

    let tid = create_tracking_id();
    event!(
        name: "shipping.tracking_id.created",
        Level::INFO,
        demo.shipping.tracking.id = tid.as_str(),
        "Shipment created, tracking id {} in {} ms",
        tid,
        start.elapsed().as_millis()
    );
    HttpResponse::Ok().json(ShipOrderResponse { tracking_id: tid })
}

#[cfg(test)]
mod tests {
    use actix_web::{http::header::ContentType, test, App};
    use open_feature::provider::{MockFeatureProvider, ResolutionDetails};
    use std::collections::HashMap;
    use std::sync::{Arc, Mutex};
    use tracing::{field::Visit, Event, Subscriber};
    use tracing_subscriber::{layer::Context, prelude::*, Layer};

    use super::*;

    #[derive(Default)]
    struct Fields {
        values: HashMap<String, String>,
    }

    impl Visit for Fields {
        fn record_debug(&mut self, field: &tracing::field::Field, value: &dyn std::fmt::Debug) {
            self.values
                .insert(field.name().to_string(), format!("{value:?}"));
        }
    }

    #[derive(Clone, Default)]
    struct CapturedEvents(Arc<Mutex<Vec<(String, Level, Fields)>>>);

    impl<S: Subscriber> Layer<S> for CapturedEvents {
        fn on_event(&self, event: &Event<'_>, _ctx: Context<'_, S>) {
            let mut fields = Fields::default();
            event.record(&mut fields);
            self.0.lock().unwrap().push((
                event.metadata().name().to_string(),
                *event.metadata().level(),
                fields,
            ));
        }
    }

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
        let app = test::init_service(App::new().app_data(provider).service(ship_order)).await;
        let req = test::TestRequest::post()
            .uri("/ship-order")
            .insert_header(ContentType::json())
            .set_json(&ShipOrderRequest {
                address,
                items: vec![],
            })
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
    async fn test_destination_country() {
        assert_eq!(destination_country(None), "unknown");
        assert_eq!(destination_country(Some(&make_address("  "))), "unknown");
        assert_eq!(destination_country(Some(&make_address(" usa "))), "USA");
        assert_eq!(
            destination_country(Some(&make_address("United States"))),
            "UNITED STATES"
        );
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
        let captured = CapturedEvents::default();
        let subscriber = tracing_subscriber::registry().with(captured.clone());
        let _guard = tracing::subscriber::set_default(subscriber);
        let start = std::time::Instant::now();
        let order = call_ship_order(Some(make_address("FR")), mock_provider(1)).await;
        assert!(start.elapsed() >= std::time::Duration::from_secs(1));
        assert!(!order.tracking_id.is_empty());
        let events = captured.0.lock().unwrap();
        let slowdown = events
            .iter()
            .find(|(name, _, _)| name == "shipping.international.slowdown")
            .unwrap();
        assert_eq!(slowdown.1, Level::WARN);
        assert_eq!(
            slowdown.2.values.get("demo.shipping.delay_ms").unwrap(),
            "1000"
        );
        let tracking = events
            .iter()
            .find(|(name, _, _)| name == "shipping.tracking_id.created")
            .unwrap();
        assert_eq!(tracking.1, Level::INFO);
        assert_eq!(
            tracking.2.values.get("demo.shipping.tracking.id").unwrap(),
            &format!("{:?}", order.tracking_id)
        );
    }

    #[actix_web::test]
    async fn test_ship_order_rejects_invalid_slowdown() {
        let captured = CapturedEvents::default();
        let subscriber = tracing_subscriber::registry().with(captured.clone());
        let _guard = tracing::subscriber::set_default(subscriber);
        for value in [-1, 11, i64::MAX] {
            let order = actix_web::rt::time::timeout(
                std::time::Duration::from_secs(1),
                call_ship_order(Some(make_address("FR")), mock_provider(value)),
            )
            .await
            .expect("invalid slowdown must not delay the request");
            assert!(!order.tracking_id.is_empty());
        }
        let events = captured.0.lock().unwrap();
        let invalid: Vec<_> = events
            .iter()
            .filter(|(name, _, _)| name == "shipping.international.invalid_slowdown")
            .collect();
        assert_eq!(invalid.len(), 3);
        for (event, value) in invalid.iter().zip([-1_i64, 11, i64::MAX]) {
            assert_eq!(event.1, Level::ERROR);
            assert_eq!(
                event.2.values.get("slowdown_secs").unwrap(),
                &value.to_string()
            );
        }
        assert!(!events
            .iter()
            .any(|(name, _, _)| name == "shipping.international.slowdown"));
    }

    #[actix_web::test]
    async fn test_ship_order_us_flag_on() {
        let start = std::time::Instant::now();
        let order = call_ship_order(Some(make_address("US")), mock_provider(10)).await;
        assert!(start.elapsed() < std::time::Duration::from_secs(1));
        assert!(!order.tracking_id.is_empty());
    }
}
