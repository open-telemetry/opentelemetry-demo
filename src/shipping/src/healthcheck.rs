// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use std::env;
use std::net::TcpStream;
use std::process;

fn main() {
    let port = env::var("SHIPPING_PORT").unwrap_or_else(|_| "50050".to_string());
    match TcpStream::connect(format!("127.0.0.1:{}", port)) {
        Ok(_) => process::exit(0),
        Err(_) => process::exit(1),
    }
}
