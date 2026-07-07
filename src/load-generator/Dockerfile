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

# Runtime stage: reuse Grafana's official k6 browser image. k6's browser module
# is very sensitive to the Chromium build it launches — Debian's Chromium
# crashes on startup (SIGTRAP), whereas this image ships an Alpine + Chromium
# combination that Grafana tests against the matching k6 release. Pin the tag to
# our k6 version (built above) so the base's Chromium tracks a compatible k6.
# We only swap in our own k6 binary: the stock one here lacks the xk6-otel
# extension that script.js imports as `k6/x/otel`.
FROM grafana/k6:2.0.0-with-browser

# Overwrite the stock k6 with our extension-enabled, statically-linked build
# (it runs unchanged on this Alpine/musl base).
COPY --from=builder /build/k6 /usr/bin/k6

WORKDIR /home/k6
COPY ./src/load-generator/script.js .
COPY ./src/load-generator/people.json .

# --out opentelemetry sends k6 test metrics to the OTel Collector via OTLP.
# The collector endpoint and protocol are configured in compose.yaml via the
# K6_OTEL_* env vars consumed by this built-in k6 output.
ENTRYPOINT ["k6", "run", "script.js", "--out", "opentelemetry"]
