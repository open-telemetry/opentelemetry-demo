# Shipping Service

The Shipping service queries `quote` for price quote, provides tracking IDs,
and the impression of order fulfillment & shipping processes.

## Local

This repo assumes you have rust 1.82 installed. You may use docker, or
[install rust](https://www.rust-lang.org/tools/install).

## Build

From `../../`, run:

```sh
docker compose build shipping
```

## Test

```sh
cargo test
```

## Feature Flags

* `shippingSlowdown`: when enabled, non-US shipping requests are delayed by 10
  seconds to simulate overseas shipping latency. US addresses are never affected.
  The flag is evaluated via the flagd OFREP REST API.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLAGD_HOST` | `flagd` | Hostname of the flagd service |
| `FLAGD_OFREP_PORT` | `8016` | Port for the flagd OFREP API |
