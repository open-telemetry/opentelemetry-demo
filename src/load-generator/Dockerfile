# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Build stage: compile a custom k6 binary that includes the OTel extension.
# k6 v2 requires Go 1.25; xk6 is the official k6 extension build tool.
FROM golang:1.25-bookworm AS builder

# Install xk6. Pin this version when you pin k6 itself.
RUN go install go.k6.io/xk6/cmd/xk6@latest

WORKDIR /build

# Copy the extension source before running xk6 so it can be provided as a
# local module via the --with flag rather than fetched from a remote registry.
COPY ./src/load-generator/xk6-otel ./xk6-otel

RUN xk6 build v2.0.0 \
    --with github.com/open-telemetry/opentelemetry-demo/src/load-generator/xk6-otel=./xk6-otel \
    --output ./k6

# Runtime stage: nothing but the binary and the test assets.
FROM debian:bookworm-slim

RUN apt-get -qq update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        chromium \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/k6 /usr/local/bin/k6

WORKDIR /usr/src/app/
COPY ./src/load-generator/script.js .
COPY ./src/load-generator/people.json .

# --out opentelemetry sends k6 test metrics to the OTel Collector via OTLP.
# The collector endpoint and protocol are configured in compose.yaml via the
# K6_OTEL_* env vars consumed by this built-in k6 output.
ENTRYPOINT ["k6", "run", "script.js", "--out", "opentelemetry"]
