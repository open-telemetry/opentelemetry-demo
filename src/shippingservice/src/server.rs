use tonic::{transport::Server};

mod shipping_service;
use shipping_service::ShippingServer;
use shipping_service::shop::shipping_service_server::{ShippingServiceServer};

mod health_service;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "[::1]:50051".parse()?;
    let shipper = ShippingServer::default();

    Server::builder()
        .add_service(ShippingServiceServer::new(shipper))
        .serve(addr)
        .await?;
    
    Ok(())
}