# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.19.2-alpine AS builder
RUN apk add build-base protobuf-dev protoc
RUN apk add --no-cache git

WORKDIR /usr/src/app/

# Restore dependencies
COPY ./src/accountingservice/ ./
COPY ./pb/ ./proto/

ENV GOPROXY=direct
ENV GOSUMDB=off

RUN go mod download
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.2

# Build executable
RUN protoc -I ./proto/ ./proto/demo.proto --go_out=./ --go-grpc_out=./
RUN go build -o /go/bin/accountingservice/ ./

# -----------------------------------------------------------------------------

FROM alpine

WORKDIR /usr/src/app/

COPY --from=builder /go/bin/accountingservice/ ./

ENTRYPOINT [ "./accountingservice" ]
