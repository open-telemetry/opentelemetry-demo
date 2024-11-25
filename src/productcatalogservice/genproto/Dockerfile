# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM golang:1.22-alpine

WORKDIR /build

RUN apk add --no-cache protobuf-dev

COPY ./src/productcatalogservice/go.mod ./
COPY ./src/productcatalogservice/go.sum ./
COPY ./src/productcatalogservice/tools.go ./

RUN go env -w GOMODCACHE=/root/.cache/go-build
RUN --mount=type=cache,target=/root/.cache/go-build \
    go list -e -f '{{range .Imports}}{{.}} {{end}}' tools.go | CGO_ENABLED=0 xargs go install -mod=readonly \
