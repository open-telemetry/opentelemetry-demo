#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# update-docker.sh
#
# Purpose:
#   Updates the Docker Compose configuration for the OpenTelemetry Demo
#   by copying, modifying, and customizing the original file for New Relic
#   compatibility.
#
# How to run:
#   ./update-docker.sh
#   (Run from the newrelic/scripts directory)
#
# Dependencies:
#   - Docker
#   - yq (YAML processor)
#   - Access to the project source and Docker Compose files
# -----------------------------------------------------------------------------
set -euo pipefail

source "$(dirname "$0")/common.sh"
check_tool_installed docker

# Copy the YAML file
cp "$DOCKER_COMPOSE_PATH" "$NR_DOCKER_COMPOSE_PATH"

# delete containers that are not required
yq eval -i 'del(.services.grafana)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.jaeger)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.prometheus)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.opensearch)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.frontendTests)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.traceBasedTests)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.tracetest-server)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.tracetest-postgres)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.frontend-proxy.depends_on.jaeger)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.frontend-proxy.depends_on.grafana)' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.otel-collector.depends_on)' "$NR_DOCKER_COMPOSE_PATH"

# add environment variables required by the OpenTelemetry Collector
yq eval -i '.services.otel-collector.environment += [ "NEW_RELIC_LICENSE_KEY=${NEW_RELIC_LICENSE_KEY}" ]' "$NR_DOCKER_COMPOSE_PATH"

# update the command used to launch the collector to point to the NR-specific config
yq eval -i '.services.otel-collector.command[0] = "--config=/etc/otelcol-config.yml" ' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i 'del(.services.otel-collector.command[1])' "$NR_DOCKER_COMPOSE_PATH"

yq eval -i '.services.otel-collector.volumes = [ "${HOST_FILESYSTEM}:/hostfs:ro", "${DOCKER_SOCK}:/var/run/docker.sock:ro", "../docker/config/otel-config-docker.yaml:/etc/otelcol-config.yml", "./logs:/logs", "./checkpoint:/checkpoint" ]' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i '.services.flagd.volumes = [ "${SRC_DIR}/flagd:/etc/flagd" ]' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i '.services.flagd-ui.volumes = [ "${SRC_DIR}/flagd:/app/data" ]' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i '.services.product-catalog.volumes = [ "${SRC_DIR}/product-catalog/products:/usr/src/app/products" ]' "$NR_DOCKER_COMPOSE_PATH"

# add ports used by the OpenTelemetry Collector
yq eval -i '.services.otel-collector.ports += [ "8888" ]' "$NR_DOCKER_COMPOSE_PATH"
yq eval -i '.services.otel-collector.ports += [ "13133" ]' "$NR_DOCKER_COMPOSE_PATH"

echo "Completed updating ./docker/docker-compose.yml for the OpenTelemetry demo app!"
