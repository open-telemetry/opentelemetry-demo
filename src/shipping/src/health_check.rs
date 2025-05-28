use actix_web::{get, Responder, HttpResponse};

#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().body("healthy: SERVING")
}
