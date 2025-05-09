# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM --platform=$BUILDPLATFORM golang:1.22-alpine AS builder

WORKDIR /usr/src/app/

# Copy go mod files
COPY src/product-catalog/go.sum src/product-catalog/go.mod ./

# Download dependencies
RUN go mod download

COPY src/product-catalog/ ./

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags "-s -w" -o /go/bin/product-catalog/ ./

FROM --platform=$TARGETPLATFORM debian:bullseye-slim AS release

WORKDIR /usr/src/app/

# Install basic tools for debugging
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    procps \
    bash \
    && rm -rf /var/lib/apt/lists/* \
    && which bash \
    && ls -l /bin/bash

COPY --from=builder /go/bin/product-catalog/ ./

EXPOSE ${PRODUCT_CATALOG_PORT}
ENTRYPOINT [ "./product-catalog" ]
