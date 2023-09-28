# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM envoyproxy/envoy:v1.27-latest

USER envoy
WORKDIR /home/envoy
COPY ./src/frontendproxy/envoy.tmpl.yaml envoy.tmpl.yaml

ENTRYPOINT ["/bin/sh", "-c", "envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml;"]
