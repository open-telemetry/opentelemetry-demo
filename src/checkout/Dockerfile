# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/golang:1.27.0-bookworm@sha256:ded31c68586d2e49e760acc2e65a884b23d032e9bbbed0ae0c55abd3fcaf4452 AS builder

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

FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.56@sha256:d4d9b3d32e3ebe1c14e04564cdcc5470233893d39acea1ed99fc46879dd2e838 AS grpc-health-probe

FROM gcr.io/distroless/static-debian12:nonroot@sha256:afa5c872c891853ca7fcf1f12c3edb23f7eeef36189728842dd51042ff57f7ab

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/checkout/ ./
COPY --from=grpc-health-probe /ko-app/grpc-health-probe /bin/grpc_health_probe

EXPOSE ${CHECKOUT_PORT}
ENTRYPOINT [ "./checkout" ]
