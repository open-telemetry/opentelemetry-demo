# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM envoyproxy/envoy:v1.38.2@sha256:af7c3dfdbe10de65cb2db5839ce1adf8904ee41c9d372076d62acab43af6ec41

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
