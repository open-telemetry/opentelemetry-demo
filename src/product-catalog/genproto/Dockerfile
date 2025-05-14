# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM golang:1.24-alpine

WORKDIR /build

RUN apk add --no-cache protobuf-dev

COPY ./src/product-catalog/go.mod go.mod
COPY ./src/product-catalog/go.sum go.sum

RUN go install tool
