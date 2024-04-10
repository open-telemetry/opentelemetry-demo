# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.22-alpine AS builder

WORKDIR /usr/src/app/

RUN apk update \
    && apk add --no-cache make protobuf-dev

RUN --mount=type=cache,target=/go/pkg/mod/ \
    --mount=type=bind,source=./src/checkoutservice/go.sum,target=go.sum \
    --mount=type=bind,source=./src/checkoutservice/go.mod,target=go.mod \
    --mount=type=bind,source=./src/checkoutservice/tools.go,target=tools.go \
    go mod download \
    && go list -e -f '{{range .Imports}}{{.}} {{end}}' tools.go | CGO_ENABLED=0 xargs go install -mod=readonly

RUN --mount=type=cache,target=/go/pkg/mod/ \
    --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=bind,rw,source=./src/checkoutservice,target=. \
    --mount=type=bind,rw,source=./pb,target=./pb \
    protoc -I ./pb ./pb/demo.proto --go_out=./ --go-grpc_out=./ \
    && go build -ldflags "-s -w" -o /go/bin/checkoutservice/ ./

FROM alpine

WORKDIR /usr/src/app/

COPY --from=builder /go/bin/checkoutservice/ ./

EXPOSE ${CHECKOUT_SERVICE_PORT}
ENTRYPOINT [ "./checkoutservice" ]
