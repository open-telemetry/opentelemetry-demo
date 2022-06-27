use tonic::{transport::Server};

mod shipping_service;
use shipping_service::ShippingServer;
use shipping_service::shop::shipping_service_server::ShippingServiceServer;

mod health_service;
use health_service::HealthCheckServer;
use health_service::health::health_server::HealthServer;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "[::1]:50051".parse()?;
    let shipper = ShippingServer::default();
    let health = HealthCheckServer::default();

    Server::builder()
        .add_service(ShippingServiceServer::new(shipper))
        .add_service(HealthServer::new(health))
        .serve(addr)
        .await?;
    
    Ok(())
}