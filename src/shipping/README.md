# Shipping Service

The Shipping service queries `quote` for price quote, provides tracking IDs,
and the impression of order fulfillment & shipping processes.

## Local

This repo assumes you have rust 1.73 installed. You may use docker, or install
rust [here](https://www.rust-lang.org/tools/install).

## Build

From `../../`, run:

```sh
docker compose build shipping
```

## Test

```sh
cargo test
```
