# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.22-alpine AS builder

WORKDIR /usr/src/app/

RUN --mount=type=cache,target=/go/pkg/mod/ \
    --mount=type=bind,source=./src/product-catalog/go.sum,target=go.sum \
    --mount=type=bind,source=./src/product-catalog/go.mod,target=go.mod \
    go mod download

RUN --mount=type=cache,target=/go/pkg/mod/ \
    --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=bind,rw,source=./src/product-catalog,target=. \
    go build -ldflags "-s -w" -o /go/bin/product-catalog/ ./

FROM alpine AS release

WORKDIR /usr/src/app/

COPY ./src/product-catalog/products/ ./products/
COPY --from=builder /go/bin/product-catalog/ ./

EXPOSE ${PRODUCT_CATALOG_PORT}
ENTRYPOINT [ "./product-catalog" ]
