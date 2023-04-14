# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.19.2-alpine AS builder
RUN apk add build-base protobuf-dev protoc
WORKDIR /usr/src/app/

# Restore dependencies
COPY ./src/checkoutservice-v2/ ./
COPY ./pb/ ./proto/
RUN go mod download
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.2

# Build executable
RUN protoc -I ./proto/ ./proto/demo.proto --go_out=./ --go-grpc_out=./
RUN go build -o /go/bin/checkoutservice-v2 ./

# -----------------------------------------------------------------------------

FROM alpine

WORKDIR /usr/src/app/

COPY --from=builder /go/bin/checkoutservice-v2 ./

EXPOSE ${CHECKOUT_SERVICE_PORT}
ENTRYPOINT [ "./checkoutservice-v2" ]
