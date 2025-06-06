// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
pub struct CartItem {
    pub quantity: u32,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Address {
    pub zip_code: String,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct GetQuoteRequest {
    pub items: Vec<CartItem>,
    pub address: Option<Address>,
}

#[derive(Debug, Serialize)]
pub struct Money {
    pub currency_code: String,
    pub units: u64,
    pub nanos: u32,
}

#[derive(Debug, Serialize)]
pub struct GetQuoteResponse {
    pub cost_usd: Option<Money>,
}

#[derive(Debug, Default)]
pub struct Quote {
    pub dollars: u64,
    pub cents: u32,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct ShipOrderRequest {}

#[derive(Debug, Deserialize, Serialize)]
pub struct ShipOrderResponse {
    pub tracking_id: String,
}
