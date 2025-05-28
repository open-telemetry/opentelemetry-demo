// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct CartItem {
    pub quantity: u32,
}

#[derive(Debug, Deserialize)]
pub struct Address {
    pub zip_code: String,
}

#[derive(Debug, Deserialize)]
pub struct GetQuoteRequest {
    pub items: Vec<CartItem>,
    pub address: Option<Address>,
}

#[derive(Debug, Serialize)]
pub struct Money {
    pub currency_code: String,
    pub units: i64,
    pub nanos: i32,
}

#[derive(Debug, Serialize)]
pub struct GetQuoteResponse {
    pub cost_usd: Option<Money>,
}

#[derive(Debug, Deserialize)]
pub struct ShipOrderRequest {}

#[derive(Debug, Serialize)]
pub struct ShipOrderResponse {
    pub tracking_id: String,
}
