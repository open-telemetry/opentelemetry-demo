// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

mod resources_conf;
pub use resources_conf::get_resource_attr;

mod traces_conf;
pub use traces_conf::init_reqwest_tracing;
pub use traces_conf::init_tracer;

mod logs_conf;
pub use logs_conf::init_logger;
