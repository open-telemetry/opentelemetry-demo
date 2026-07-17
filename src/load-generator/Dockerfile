# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Build stage: compile a custom k6 binary that includes the OTel extension.
# k6 v2 requires Go 1.25; xk6 is the official k6 extension build tool.
FROM docker.io/library/golang:1.26.5-bookworm@sha256:1ecb7edf62a0408027bd5729dfd6b1b8766e578e8df93995b225dfd0944eb651 AS builder

# xk6 is the build tool, not part of the runtime image; pin to a known-good
# release independent of the k6 version being built below.
RUN go install go.k6.io/xk6/cmd/xk6@v1.4.7

WORKDIR /build

# Copy the extension source before running xk6 so it can be provided as a
# local module via the --with flag rather than fetched from a remote registry.
COPY ./src/load-generator/xk6-otel ./xk6-otel

RUN xk6 build v2.1.0 \
    --with github.com/open-telemetry/opentelemetry-demo/src/load-generator/xk6-otel=./xk6-otel \
    --output ./k6

# Runtime on Grafana's k6 browser image for a working headless Chromium
# (Debian's Chromium crashes on startup). Its stock k6 lacks the xk6-otel
# extension script.js needs, so overwrite it with the build from above.
FROM docker.io/grafana/k6:2.1.0-with-browser@sha256:40612240f5e37819faedb12b1df4e2cfbd7b0894475ff3c8b8f8f05239b7aff6

COPY --from=builder /build/k6 /usr/bin/k6

WORKDIR /home/k6
COPY ./src/load-generator/script.js .
COPY ./src/load-generator/people.json .
COPY --chmod=755 ./src/load-generator/entrypoint.sh .

# entrypoint.sh wraps k6 to support flagd-driven VU restarts
ENTRYPOINT ["./entrypoint.sh"]
