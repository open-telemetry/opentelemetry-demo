# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM envoyproxy/envoy:v1.34-latest

RUN apt-get update && \
    apt-get install -y gettext-base && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./src/frontend-proxy/envoy.tmpl.yaml /home/envoy/envoy.tmpl.yaml
COPY ./src/frontend-proxy/start-envoy.sh /home/envoy/start-envoy.sh

RUN chmod +x /home/envoy/start-envoy.sh && \
    chown -R envoy:envoy /home/envoy

USER envoy

WORKDIR /home/envoy

ENTRYPOINT ["./start-envoy.sh"]
