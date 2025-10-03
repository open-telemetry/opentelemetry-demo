# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM envoyproxy/envoy:v1.34-latest

RUN apt-get update && \
    apt-get install -y gettext-base && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER envoy

WORKDIR /home/envoy

COPY ./src/frontend-proxy/envoy.tmpl.yaml envoy.tmpl.yaml

# Set default value for OTEL_* config if not provided by Docker Compose or K8s
ENV OTEL_SERVICE_NAME="frontend-proxy"
ENV OTEL_COLLECTOR_HOST=localhost
ENV OTEL_COLLECTOR_PORT_GRPC=4317
ENV OTEL_COLLECTOR_PORT_HTTP=4318

EXPOSE ${ENVOY_PORT}
EXPOSE ${ENVOY_ADMIN_PORT}
ENTRYPOINT ["/bin/sh", "-c", "envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml;"]
