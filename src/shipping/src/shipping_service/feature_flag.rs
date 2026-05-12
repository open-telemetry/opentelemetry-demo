// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use awc::Client;
use opentelemetry_instrumentation_actix_web::ClientExt;
use serde::Deserialize;
use std::cell::RefCell;
use std::env;
use tracing::warn;

thread_local! {
    static HTTP_CLIENT: RefCell<Option<Client>> = const { RefCell::new(None) };
}

fn get_client() -> Client {
    HTTP_CLIENT.with(|cell| {
        let mut opt = cell.borrow_mut();
        if opt.is_none() {
            *opt = Some(Client::default());
        }
        opt.as_ref().unwrap().clone()
    })
}

#[derive(Debug, Deserialize)]
struct OFREPResponse {
    value: bool,
    variant: Option<String>,
}

#[derive(Clone)]
pub struct FlagdClient {
    base_url: String,
}

impl FlagdClient {
    pub fn from_env() -> Self {
        let host = env::var("FLAGD_HOST").unwrap_or_else(|_| "flagd".to_string());
        let port = env::var("FLAGD_OFREP_PORT")
            .ok()
            .and_then(|p| p.parse::<u16>().ok())
            .unwrap_or(8016);

        Self {
            base_url: format!("http://{}:{}/ofrep/v1/evaluate/flags", host, port),
        }
    }

    pub async fn is_enabled(&self, flag_name: &str) -> bool {
        let url = format!("{}/{}", self.base_url, flag_name);

        let result = get_client()
            .post(&url)
            .insert_header(("Content-Type", "application/json"))
            .trace_request()
            .send_body(r#"{"context":{}}"#)
            .await;

        match result {
            Ok(mut resp) if resp.status().is_success() => {
                match resp.json::<OFREPResponse>().await {
                    Ok(data) => data.value,
                    Err(e) => {
                        warn!("Failed to parse feature flag response for {}: {}", flag_name, e);
                        false
                    }
                }
            }
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
}
