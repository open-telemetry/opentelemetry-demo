// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use awc::Client;
use opentelemetry::{
    global,
    trace::{Span, SpanKind, Tracer},
    KeyValue,
};
use opentelemetry_instrumentation_actix_web::ClientExt;
use serde::Deserialize;
use std::env;
use tracing::warn;

#[derive(Debug, Deserialize)]
struct OFREPResponse {
    value: bool,
    variant: Option<String>,
}

/// Checks whether a boolean feature flag is enabled via the flagd OFREP REST API.
/// Returns `false` on any error so the service degrades gracefully.
pub async fn is_feature_flag_enabled(flag_name: &str) -> bool {
    let tracer = global::tracer("otel_demo.shipping.feature_flag");
    let mut span = tracer
        .span_builder(format!("feature_flag {}", flag_name))
        .with_kind(SpanKind::Client)
        .start(&tracer);

    span.set_attribute(KeyValue::new("feature_flag.key", flag_name.to_string()));
    span.set_attribute(KeyValue::new("feature_flag.provider_name", "flagd"));

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
        Ok(mut resp) => match resp.json::<OFREPResponse>().await {
            Ok(data) => {
                if let Some(variant) = &data.variant {
                    span.set_attribute(KeyValue::new(
                        "feature_flag.variant",
                        variant.clone(),
                    ));
                }
                data.value
            }
            Err(e) => {
                warn!(
                    "Failed to parse feature flag response for {}: {}",
                    flag_name, e
                );
                false
            }
        },
        Err(e) => {
            warn!("Failed to check feature flag {}: {}", flag_name, e);
            false
        }
    }
}
