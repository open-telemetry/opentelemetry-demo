// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use uuid::Uuid;

/// returns a tracking ID
pub fn create_tracking_id() -> String {
    Uuid::new_v4().to_string()
}
