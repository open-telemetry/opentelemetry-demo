# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM envoyproxy/envoy-dev:8c202194ac6a2cb781eb6ce27d924b379b1e787f
RUN apt-get update && apt-get install -y gettext-base && apt-get clean && rm -rf /var/lib/apt/lists/*

USER envoy
WORKDIR /home/envoy
COPY ./src/frontendproxy/envoy.tmpl.yaml envoy.tmpl.yaml

ENTRYPOINT ["/bin/sh", "-c", "envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml;"]
