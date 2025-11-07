// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
pub struct CartItem {
    #[serde(alias = "productId")]
    pub product_id: String,
    pub quantity: u32,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Address {
    #[serde(alias = "streetAddress")]
    pub street_address: String,
    pub city: String,
    pub state: String,
    pub country: String,
    #[serde(alias = "zipCode")]
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
pub struct ShipOrderRequest {
    pub address: Option<Address>,
    pub items: Vec<CartItem>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct ShipOrderResponse {
    pub tracking_id: String,
}
