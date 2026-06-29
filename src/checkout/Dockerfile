# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/golang:1.26.4-bookworm@sha256:b305420a68d0f229d91eb3b3ed9e519fcf2cf5461da4bef997bf927e8c0bfd2b AS builder

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

FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.52@sha256:0303b506a288d544ed99fef17a55c8c5ce872f498f643c396b532b3595089ac9 AS grpc-health-probe

FROM gcr.io/distroless/static-debian12:nonroot@sha256:d093aa3e30dbadd3efe1310db061a14da60299baff8450a17fe0ccc514a16639

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/checkout/ ./
COPY --from=grpc-health-probe /ko-app/grpc-health-probe /bin/grpc_health_probe

EXPOSE ${CHECKOUT_PORT}
ENTRYPOINT [ "./checkout" ]
