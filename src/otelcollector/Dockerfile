# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM golang:latest as build

ARG TARGETARCH
ARG BUILDER_VERSION=0.81.0

RUN curl -L -o /builder https://github.com/open-telemetry/opentelemetry-collector/releases/download/cmd%2Fbuilder%2Fv${BUILDER_VERSION}/ocb_${BUILDER_VERSION}_linux_${TARGETARCH}
RUN chmod +x /builder
WORKDIR /build
COPY ./src/otelcollector/manifest.yml ./
ENV GOARCH=$TARGETARCH
ENV CGO_ENABLED=0
RUN /builder --config ./manifest.yml --output-path /build/_build
RUN ls /build/_build

FROM alpine:3.16 as certs
RUN apk --update add ca-certificates

FROM alpine

ARG USER_UID=10001
USER ${USER_UID}

COPY --from=certs /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=build --chmod=755 /build/_build/otelcol-demo /otelcol-demo
COPY ./src/otelcollector/otelcol-*.yml /etc/otelcol/
ENTRYPOINT ["/otelcol-demo"]
CMD ["--config", "/etc/otelcol/otelcol-config.yml"]
EXPOSE 4317 4318
