# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM envoyproxy/envoy-dev:6ef1bb476da8d050347b462b2d8efa1cddeb420f
RUN apt-get update && apt-get install -y gettext-base && apt-get clean && rm -rf /var/lib/apt/lists/*

USER envoy
WORKDIR /home/envoy
COPY ./src/frontendproxy/envoy.tmpl.yaml envoy.tmpl.yaml

ENTRYPOINT ["/bin/sh", "-c", "envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml;"]
