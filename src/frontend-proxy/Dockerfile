# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM envoyproxy/envoy:v1.38.1@sha256:4e3c734cbe9892a3513c97cf3974ff73cfef5d784f5cceed9ea758a2b80e0c31

RUN apt-get update && \
    apt-get install -y gettext-base && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER envoy

WORKDIR /home/envoy

COPY ./src/frontend-proxy/envoy.tmpl.yaml envoy.tmpl.yaml

EXPOSE ${ENVOY_PORT}
EXPOSE ${ENVOY_ADMIN_PORT}
ENTRYPOINT ["/bin/sh", "-c", "envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml;"]
