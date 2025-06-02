// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use actix_web::{get, HttpResponse, Responder};

#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().body("healthy: SERVING")
}
