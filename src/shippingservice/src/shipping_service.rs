use opentelemetry::trace::TraceContextExt;
use opentelemetry::trace::Tracer;
use opentelemetry::{global, KeyValue};
use shop::shipping_service_server::ShippingService;
use shop::{GetQuoteRequest, GetQuoteResponse, Money, ShipOrderRequest, ShipOrderResponse};
use tonic::{Request, Response, Status};

use log::*;

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

const NANOS_MULTIPLE: i32 = 10000000i32;

pub mod shop {
    tonic::include_proto!("hipstershop"); // The string specified here must match the proto package name
}

#[derive(Debug, Default)]
pub struct ShippingServer {}

#[tonic::async_trait]
impl ShippingService for ShippingServer {
    async fn get_quote(
        &self,
        request: Request<GetQuoteRequest>,
    ) -> Result<Response<GetQuoteResponse>, Status> {
        info!("GetQuoteRequest: {:?}", request);

        let itemct: u32 = request
            .into_inner()
            .items
            .into_iter()
            .fold(0, |accum, cart_item| accum + (cart_item.quantity as u32));

        // We may want to ask another service for product pricing / info
        // (although now everything is assumed to be the same price)
        // check out the create_quote_from_count method to see how we use the span created here
        let q = global::tracer("shippingservice/get-quote")
            .in_span("get-quote", |_cx| create_quote_from_count(itemct));
        let reply = GetQuoteResponse {
            cost_usd: Some(Money {
                currency_code: "USD".into(),
                units: q.dollars,
                nanos: q.cents * NANOS_MULTIPLE,
            }),
        };
        info!("Sending Quote: {}", q);

        Ok(Response::new(reply))
    }
    async fn ship_order(
        &self,
        request: Request<ShipOrderRequest>,
    ) -> Result<Response<ShipOrderResponse>, Status> {
        info!("ShipOrderRequest: {:?}", request);

        // in this case, generating a tracking ID is trivial
        // we'll create a span and associated events all in this function.
        let reply = global::tracer("shippingservice/ship-order").in_span("ship-order", |cx| {
            let tid = create_tracking_id();
            cx.span()
                .add_event("Tracking ID issued", vec![KeyValue::new(tid.clone(), true)]);
            info!("Tracking ID Created: {}", tid);
            ShipOrderResponse { tracking_id: tid }
        });

        Ok(Response::new(reply))
    }
}

#[cfg(test)]
mod tests {
    use super::{
        shop::shipping_service_server::ShippingService,
        shop::{Address, GetQuoteRequest},
        shop::{CartItem, ShipOrderRequest},
        ShippingServer, NANOS_MULTIPLE,
    };
    use tonic::Request;
    use uuid::Uuid;

    fn make_quote_request_with_items(items: Vec<i32>) -> Request<GetQuoteRequest> {
        let cart_items: Vec<CartItem> = items.into_iter().fold(Vec::new(), |mut accum, count| {
            accum.push(CartItem {
                product_id: "fake-item".to_string(),
                quantity: count,
            });
            accum
        });

        Request::new(GetQuoteRequest {
            address: Some(Address::default()),
            items: cart_items,
        })
    }

    fn make_empty_quote_request() -> Request<GetQuoteRequest> {
        Request::new(GetQuoteRequest::default())
    }
    #[tokio::test]
    async fn empty_quote() {
        let server = ShippingServer::default();

        // when we provide no items, the quote should be empty
        match server.get_quote(make_empty_quote_request()).await {
            Ok(resp) => {
                let money = resp.into_inner().cost_usd.unwrap();
                assert_eq!(money.units, 0);
                assert_eq!(money.nanos, 0);
            }
            Err(e) => panic!("error when making empty quote request: {}", e),
        }
    }

    #[tokio::test]
    async fn quote_for_one_value() {
        let server = ShippingServer::default();

        match server
            .get_quote(make_quote_request_with_items(vec![1_i32]))
            .await
        {
            Ok(resp) => {
                // items are fixed at 8.99, so we should see that price reflected.
                let money = resp.into_inner().cost_usd.unwrap();
                assert_eq!(money.units, 8);
                assert_eq!(money.nanos, 99 * NANOS_MULTIPLE);
            }
            Err(e) => panic!("error when making quote request for one value: {}", e),
        }
    }

    #[tokio::test]
    async fn quote_for_many_values() {
        let server = ShippingServer::default();

        match server
            .get_quote(make_quote_request_with_items(vec![1_i32, 2_i32]))
            .await
        {
            Ok(resp) => {
                // items are fixed at 8.99, so we should see that price reflected for 3 items
                let money = resp.into_inner().cost_usd.unwrap();
                assert_eq!(money.units, 26);
                assert_eq!(money.nanos, 97 * NANOS_MULTIPLE);
            }
            Err(e) => panic!("error when making quote request for many values: {}", e),
        }
    }

    #[tokio::test]
    async fn can_get_tracking_id() {
        let server = ShippingServer::default();

        match server
            .ship_order(Request::new(ShipOrderRequest::default()))
            .await
        {
            Ok(resp) => {
                // we should see a uuid
                match Uuid::parse_str(&resp.into_inner().tracking_id) {
                    Ok(_) => {}
                    Err(e) => panic!("error when parsing uuid: {}", e),
                }
            }
            Err(e) => panic!("error when making request for tracking ID: {}", e),
        }
    }
}
