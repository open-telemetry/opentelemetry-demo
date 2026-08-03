# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/golang:1.26.5-bookworm@sha256:1ecb7edf62a0408027bd5729dfd6b1b8766e578e8df93995b225dfd0944eb651 AS builder

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

FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.53@sha256:a732f1b3a737926c2902393809b344c9f293b62f7069dbd0614caebd298b2e8d AS grpc-health-probe

FROM gcr.io/distroless/static-debian12:nonroot@sha256:f5b485ea962d9bd1186b2f6b3a061191539b905b82ec395de78cbfae51f20e35

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/checkout/ ./
COPY --from=grpc-health-probe /ko-app/grpc-health-probe /bin/grpc_health_probe

EXPOSE ${CHECKOUT_PORT}
ENTRYPOINT [ "./checkout" ]
