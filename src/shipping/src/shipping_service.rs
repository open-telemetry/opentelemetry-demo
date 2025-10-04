// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use opentelemetry::trace::{FutureExt, SpanKind, TraceContextExt, Tracer};
use opentelemetry::{global, propagation::Extractor, trace::Span, Context, KeyValue};
use opentelemetry_semantic_conventions as semconv;
use shop::shipping_service_server::ShippingService;
use shop::{GetQuoteRequest, GetQuoteResponse, Money, ShipOrderRequest, ShipOrderResponse};
use tonic::{Request, Response, Status};

use log::*;

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;

const NANOS_MULTIPLE: i32 = 10000000i32;

const RPC_SYSTEM_GRPC: &'static str = "grpc";
const RPC_SERVICE_SHIPPING: &'static str = "oteldemo.ShippingService";
const RPC_GRPC_STATUS_CODE_OK: i64 = 0;
const RPC_GRPC_STATUS_CODE_UNKNOWN: i64 = 2;

pub mod shop {
    tonic::include_proto!("oteldemo"); // The string specified here must match the proto package name
}

#[derive(Debug, Default)]
pub struct ShippingServer {}

struct MetadataMap<'a>(&'a tonic::metadata::MetadataMap);

impl<'a> Extractor for MetadataMap<'a> {
    /// Get a value for a key from the MetadataMap.  If the value can't be converted to &str, returns None
    fn get(&self, key: &str) -> Option<&str> {
        self.0.get(key).and_then(|metadata| metadata.to_str().ok())
    }

    /// Collect all the keys from the MetadataMap.
    fn keys(&self) -> Vec<&str> {
        self.0
            .keys()
            .map(|key| match key {
                tonic::metadata::KeyRef::Ascii(v) => v.as_str(),
                tonic::metadata::KeyRef::Binary(v) => v.as_str(),
            })
            .collect::<Vec<_>>()
    }
}

#[tonic::async_trait]
impl ShippingService for ShippingServer {
    async fn get_quote(
        &self,
        request: Request<GetQuoteRequest>,
    ) -> Result<Response<GetQuoteResponse>, Status> {
        debug!("GetQuoteRequest: {:?}", request);
        let parent_cx =
            global::get_text_map_propagator(|prop| prop.extract(&MetadataMap(request.metadata())));

        let request_message = request.into_inner();

        let itemct: u32 = request_message
            .items
            .into_iter()
            .fold(0, |accum, cart_item| accum + (cart_item.quantity as u32));

        // We may want to ask another service for product pricing / info
        // (although now everything is assumed to be the same price)
        // check out the create_quote_from_count method to see how we use the span created here
        let tracer = global::tracer("shipping");
        let mut span = tracer
            .span_builder("oteldemo.ShippingService/GetQuote")
            .with_kind(SpanKind::Server)
            .start_with_context(&tracer, &parent_cx);
        span.set_attribute(KeyValue::new(semconv::trace::RPC_SYSTEM, RPC_SYSTEM_GRPC));
        span.set_attribute(KeyValue::new(semconv::trace::RPC_SERVICE, RPC_SERVICE_SHIPPING));
        span.set_attribute(KeyValue::new(semconv::trace::RPC_METHOD, "GetQuote"));

        span.add_event("Processing get quote request".to_string(), vec![]);
        span.set_attribute(KeyValue::new(
            "app.shipping.zip_code",
            request_message.address.unwrap().zip_code,
        ));

        let cx = Context::current_with_span(span);
        let q = match create_quote_from_count(itemct)
            .with_context(cx.clone())
            .await
        {
            Ok(quote) => quote,
            Err(status) => {
                cx.span().set_attribute(KeyValue::new(
                    semconv::trace::RPC_GRPC_STATUS_CODE,
                    RPC_GRPC_STATUS_CODE_UNKNOWN,
                ));
                return Err(status);
            }
        };

        let reply = GetQuoteResponse {
            cost_usd: Some(Money {
                currency_code: "USD".into(),
                units: q.dollars,
                nanos: q.cents * NANOS_MULTIPLE,
            }),
        };
        info!("Sending Quote: {}", q);

        cx.span().set_attribute(KeyValue::new(
            semconv::trace::RPC_GRPC_STATUS_CODE,
            RPC_GRPC_STATUS_CODE_OK,
        ));
        Ok(Response::new(reply))
    }
    async fn ship_order(
        &self,
        request: Request<ShipOrderRequest>,
    ) -> Result<Response<ShipOrderResponse>, Status> {
        debug!("ShipOrderRequest: {:?}", request);

        let parent_cx =
            global::get_text_map_propagator(|prop| prop.extract(&MetadataMap(request.metadata())));
        // in this case, generating a tracking ID is trivial
        // we'll create a span and associated events all in this function.
        let tracer = global::tracer("shipping");
        let mut span = tracer
            .span_builder("oteldemo.ShippingService/ShipOrder")
            .with_kind(SpanKind::Server)
            .start_with_context(&tracer, &parent_cx);
        span.set_attribute(KeyValue::new(semconv::trace::RPC_SYSTEM, RPC_SYSTEM_GRPC));
        span.set_attribute(KeyValue::new(semconv::trace::RPC_SERVICE, RPC_SERVICE_SHIPPING));
        span.set_attribute(KeyValue::new(semconv::trace::RPC_METHOD, "ShipOrder"));

        span.add_event("Processing shipping order request".to_string(), vec![]);

        let tid = create_tracking_id();
        span.set_attribute(KeyValue::new("app.shipping.tracking.id", tid.clone()));
        info!("Tracking ID Created: {}", tid);

        span.add_event(
            "Shipping tracking id created, response sent back".to_string(),
            vec![],
        );

        span.set_attribute(KeyValue::new(
            semconv::trace::RPC_GRPC_STATUS_CODE,
            RPC_GRPC_STATUS_CODE_OK,
        ));
        Ok(Response::new(ShipOrderResponse { tracking_id: tid }))
    }
}

#[cfg(test)]
mod tests {
    use super::{
        shop::shipping_service_server::ShippingService, shop::ShipOrderRequest, ShippingServer,
    };
    use tonic::Request;
    use uuid::Uuid;

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
