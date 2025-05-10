# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM golang:1.22-alpine AS builder

# Install git and other build dependencies
RUN apk add --no-cache git

WORKDIR /usr/src/app/

# Copy go mod files
COPY src/checkout/go.sum src/checkout/go.mod ./

# Download dependencies
RUN go mod download

# Copy source code
COPY src/checkout/ ./

# Build for Linux
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags "-s -w" -o /go/bin/checkout/ ./

FROM alpine

WORKDIR /usr/src/app/

COPY --from=builder /go/bin/checkout/ ./

EXPOSE ${CHECKOUT_PORT}
ENTRYPOINT [ "./checkout" ]
