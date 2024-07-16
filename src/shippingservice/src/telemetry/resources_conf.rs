// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use opentelemetry_resource_detectors::{
    HostResourceDetector, OsResourceDetector, ProcessResourceDetector,
};
use opentelemetry_sdk::resource::{
    EnvResourceDetector, ResourceDetector, SdkProvidedResourceDetector, TelemetryResourceDetector,
};
use opentelemetry_sdk::Resource;
use std::time::Duration;

pub fn get_resource_attr() -> Resource {
    let env_resource = EnvResourceDetector::new().detect(Duration::from_secs(0));
    let host_resource = HostResourceDetector::default().detect(Duration::from_secs(0));
    let os_resource = OsResourceDetector.detect(Duration::from_secs(0));
    let process_resource = ProcessResourceDetector.detect(Duration::from_secs(0));
    let sdk_resource = SdkProvidedResourceDetector.detect(Duration::from_secs(0));
    let telemetry_resource = TelemetryResourceDetector.detect(Duration::from_secs(0));

    env_resource
        .merge(&host_resource)
        .merge(&os_resource)
        .merge(&process_resource)
        .merge(&sdk_resource)
        .merge(&telemetry_resource)
}
