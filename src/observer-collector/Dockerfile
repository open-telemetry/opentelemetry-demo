# check=skip=InvalidDefaultArgInFrom
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

ARG COLLECTOR_CONTRIB_IMAGE
ARG OPAMP_SUPERVISOR_IMAGE

FROM ${COLLECTOR_CONTRIB_IMAGE} AS collector

FROM ${OPAMP_SUPERVISOR_IMAGE}

USER root
RUN mkdir -p /etc/otel/supervisor-data && chown -R 10001:10001 /etc/otel

COPY --from=collector /otelcol-contrib /otelcol-contrib
COPY ./src/observer-collector/supervisor.yaml /etc/otel/supervisor.yaml
COPY ./src/observer-collector/observer-collector-config.yml /etc/otel/observer-collector-config.yml

USER 10001:10001

ENTRYPOINT ["/usr/local/bin/opampsupervisor", "--config", "/etc/otel/supervisor.yaml"]
