// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use awc::Client;
use opentelemetry_instrumentation_actix_web::ClientExt;
use serde::Deserialize;
use std::env;
use tracing::{instrument, warn, Span};

#[derive(Debug, Deserialize)]
struct OFREPResponse {
    value: bool,
    variant: Option<String>,
}

#[instrument(fields(
    otel.kind = "client",
    feature_flag.key = flag_name,
    feature_flag.provider_name = "flagd",
    feature_flag.variant = tracing::field::Empty,
))]
pub async fn is_feature_flag_enabled(flag_name: &str) -> bool {
    let host = env::var("FLAGD_HOST").unwrap_or_else(|_| "flagd".to_string());
    let port = env::var("FLAGD_OFREP_PORT")
        .ok()
        .and_then(|p| p.parse::<u16>().ok())
        .unwrap_or(8016);

    let url = format!(
        "http://{}:{}/ofrep/v1/evaluate/flags/{}",
        host, port, flag_name
    );

    let client = Client::default();
    let result = client
        .post(&url)
        .insert_header(("Content-Type", "application/json"))
        .trace_request()
        .send_body(r#"{"context":{}}"#)
        .await;

    match result {
        Ok(mut resp) if resp.status().is_success() => match resp.json::<OFREPResponse>().await {
            Ok(data) => {
                if let Some(variant) = &data.variant {
                    Span::current().record("feature_flag.variant", variant.as_str());
                }
                data.value
            }
            Err(e) => {
                warn!("Failed to parse feature flag response for {}: {}", flag_name, e);
                false
            }
        },
        Ok(resp) => {
            warn!("Feature flag {} returned HTTP {}", flag_name, resp.status());
            false
        }
        Err(e) => {
            warn!("Failed to check feature flag {}: {}", flag_name, e);
            false
        }
    }
}
