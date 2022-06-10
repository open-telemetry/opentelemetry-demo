use tonic::{Request, Response, Status};
use shop::shipping_service_server::{ShippingService};
use shop::{GetQuoteRequest,GetQuoteResponse, ShipOrderRequest,ShipOrderResponse, Money};

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
        println!("GetQuoteREquest: {:?}", request);

        let reply = GetQuoteResponse {
            cost_usd: Some(Money{
                currency_code: "USD".into(),
                units: 800i64, // replace with dollars
                nanos: 99i32 * 10000000i32, // replace with cents, leave the mutliple
            })
        };

        Ok(Response::new(reply)) // send back our formatted greeting
    }
    async fn ship_order(
        &self,
        request: Request<ShipOrderRequest>
    ) -> Result<Response<ShipOrderResponse>, Status> {
        println!("ShipOrderREquest: {:?}", request);

        let reply = ShipOrderResponse{
            tracking_id: "totally-legit-tracking-id".into(),
        };

        Ok(Response::new(reply))
    }
}