# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/golang:1.27.3-alpine@sha256:fa3d596898d9f126af7c01d14ee7597bab3f39cccf392ef36b69fe77cd681f18

WORKDIR /build

RUN apk add --no-cache protobuf-dev

COPY ./src/product-catalog/go.mod go.mod
COPY ./src/product-catalog/go.sum go.sum

RUN go install tool
