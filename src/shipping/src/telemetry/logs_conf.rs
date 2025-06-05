// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use simplelog::*;
use std::env;

pub fn init_logger() -> Result<(), log::SetLoggerError> {
    let log_level = env::var("RUST_LOG")
        .unwrap_or_else(|_| "info".to_string())
        .parse::<LevelFilter>()
        .unwrap_or(LevelFilter::Info);
    
    CombinedLogger::init(vec![
        SimpleLogger::new(log_level, Config::default()),
    ])
}
