use tonic::{Request, Response, Status};
use shop::shipping_service_server::{ShippingService};
use shop::{GetQuoteRequest,GetQuoteResponse, ShipOrderRequest,ShipOrderResponse, Money};

mod quote;
use quote::create_quote_from_count;

mod tracking;
use tracking::create_tracking_id;
pub mod shop {
    tonic::include_proto!("hipstershop"); // The string specified here must match the proto package name
}

#[derive(Debug, Default)]
pub struct ShippingServer {}

#[tonic::async_trait]
impl ShippingService for ShippingServer {
    async fn get_quote(
        &self,
        request: Request<GetQuoteRequest>
    ) -> Result<Response<GetQuoteResponse>, Status> {
        println!("GetQuoteRequest: {:?}", request);
        
        let q = create_quote_from_count(request.into_inner().items.len().try_into().unwrap());
        let reply = GetQuoteResponse {
            cost_usd: Some(Money{
                currency_code: "USD".into(),
                units: q.dollars, 
                nanos: q.cents * 10000000i32,
            })
        };

        Ok(Response::new(reply))
    }
    async fn ship_order(
        &self,
        request: Request<ShipOrderRequest>
    ) -> Result<Response<ShipOrderResponse>, Status> {
        println!("ShipOrderRequest: {:?}", request);

        let reply = ShipOrderResponse{
            tracking_id: create_tracking_id(),
        };

        Ok(Response::new(reply))
    }
}