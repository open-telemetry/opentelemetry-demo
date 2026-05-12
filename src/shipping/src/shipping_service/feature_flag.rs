// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use awc::Client;
use opentelemetry_instrumentation_actix_web::ClientExt;
use serde::de::DeserializeOwned;
use serde::Deserialize;
use std::cell::RefCell;
use std::env;
use tracing::{info, warn};

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
struct OFREPResponse<T> {
    value: T,
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

    pub async fn evaluate<T: DeserializeOwned + Default>(&self, flag_name: &str) -> T {
        let url = format!("{}/{}", self.base_url, flag_name);

        let result = get_client()
            .post(&url)
            .insert_header(("Content-Type", "application/json"))
            .trace_request()
            .send_body(r#"{"context":{}}"#)
            .await;

        match result {
            Ok(mut resp) if resp.status().is_success() => {
                match resp.json::<OFREPResponse<T>>().await {
                    Ok(data) => {
                        info!(
                            feature_flag.key = flag_name,
                            feature_flag.provider_name = "flagd",
                            feature_flag.variant = data.variant.as_deref().unwrap_or("unknown"),
                            "feature flag evaluated"
                        );
                        data.value
                    }
                    Err(e) => {
                        warn!("Failed to parse feature flag response for {}: {}", flag_name, e);
                        T::default()
                    }
                }
            }
            Ok(resp) => {
                warn!("Feature flag {} returned HTTP {}", flag_name, resp.status());
                T::default()
            }
            Err(e) => {
                warn!("Failed to check feature flag {}: {}", flag_name, e);
                T::default()
            }
        }
    }

}
