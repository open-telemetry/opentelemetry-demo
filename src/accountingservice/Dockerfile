# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.22-alpine AS builder

WORKDIR /usr/src/app

RUN apk update \
    && apk add --no-cache make protobuf-dev

RUN --mount=type=cache,target=/go/pkg/mod/ \
    --mount=type=bind,source=./src/accountingservice/go.sum,target=go.sum \
    --mount=type=bind,source=./src/accountingservice/go.mod,target=go.mod \
    --mount=type=bind,source=./src/accountingservice/tools.go,target=tools.go \
    go mod download \
    && go list -e -f '{{range .Imports}}{{.}} {{end}}' tools.go | CGO_ENABLED=0 xargs go install -mod=readonly

RUN --mount=type=cache,target=/go/pkg/mod/ \
    --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=bind,rw,source=./src/accountingservice,target=. \
    --mount=type=bind,rw,source=./pb,target=./pb \
    protoc -I ./pb ./pb/demo.proto --go_out=./ --go-grpc_out=./ \
    && go build -ldflags "-s -w" -o /go/bin/accountingservice/ ./

FROM alpine

WORKDIR /usr/src/app/

COPY --from=builder /go/bin/accountingservice/ ./

ENTRYPOINT [ "./accountingservice" ]
