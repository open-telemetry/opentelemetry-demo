# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/golang:1.27.3-bookworm@sha256:d9b6a1beb9474adc2a1ce842573639b44b2a0dd49b6669f51d3821baf9ec37c9 AS builder

WORKDIR /usr/src/app/

COPY ./src/checkout/go.mod go.mod
COPY ./src/checkout/go.sum go.sum

RUN go mod download

COPY ./src/checkout/genproto/oteldemo/ genproto/oteldemo/
COPY ./src/checkout/flags/ flags/
COPY ./src/checkout/kafka/ kafka/
COPY ./src/checkout/money/ money/
COPY ./src/checkout/main.go main.go

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags "-s -w" -o checkout main.go

FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.61@sha256:9df7b8dfbaf01d20eaedcd6de084c557074046f87cfc0413b7939ae18087c249 AS grpc-health-probe

FROM gcr.io/distroless/static-debian12:nonroot@sha256:afa5c872c891853ca7fcf1f12c3edb23f7eeef36189728842dd51042ff57f7ab

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/checkout/ ./
COPY --from=grpc-health-probe /ko-app/grpc-health-probe /bin/grpc_health_probe

ARG CHECKOUT_PORT=5050
EXPOSE ${CHECKOUT_PORT}
ENTRYPOINT [ "./checkout" ]
