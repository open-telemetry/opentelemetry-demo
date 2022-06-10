use health::health_server::{Health};
use health::{HealthCheckRequest, HealthCheckResponse};
use tonic::{Response, Status, Request};

pub mod health {
    tonic::include_proto!("grpc.health.v1");
}

pub struct HealthCheckServer;

#[tonic::async_trait]
impl Health for HealthCheckServer {
    async fn check(
        &self,
        _ : Request<HealthCheckRequest>,
    ) -> Result<Response<HealthCheckResponse>, Status>{
        let response = HealthCheckResponse {
            status: health::health_check_response::ServingStatus::Serving.into()
        };

        Ok(Response::new(response))
    }
}