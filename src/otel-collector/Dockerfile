# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

ARG COLLECTOR_CONTRIB_IMAGE=ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-contrib:0.157.0
ARG OPAMP_SUPERVISOR_IMAGE=ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-opampsupervisor:0.157.0

FROM ${COLLECTOR_CONTRIB_IMAGE} AS collector

FROM ${OPAMP_SUPERVISOR_IMAGE}

USER root
RUN mkdir -p /etc/otel/supervisor-data && \
    chown opampsupervisor:opampsupervisor /etc/otel/supervisor-data

COPY --from=collector /otelcol-contrib /otelcol-contrib
COPY --chmod=755 ./src/otel-collector/collector-entrypoint.sh /collector-entrypoint.sh
COPY ./src/otel-collector/supervisor.yaml /etc/otel/supervisor.yaml

USER opampsupervisor
ENTRYPOINT ["/usr/local/bin/opampsupervisor", "--config", "/etc/otel/supervisor.yaml"]
