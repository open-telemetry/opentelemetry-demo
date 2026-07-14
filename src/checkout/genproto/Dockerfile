# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/golang:1.26.5-alpine@sha256:0178a641fbb4858c5f1b48e34bdaabe0350a330a1b1149aabd498d0699ff5fb2

WORKDIR /build

RUN apk add --no-cache protobuf-dev

COPY ./src/checkout/go.mod go.mod
COPY ./src/checkout/go.sum go.sum

RUN go install tool
