#!/usr/bin/env bash
set -euo pipefail
# Purpose: Adapts Docker Compose files after having synced the fork with upstream.
# Notes:
#   This should be run after the OpenTelemetry Demo has been synced with the latest changes from the upstream repository.
# Requirements:
#   - yq: A portable command-line YAML processor.
#   Both can be installed using brew:
#       brew install yq
#
# Example Usage:
#   ./update-docker.sh

# Set default paths if environment variables are not set
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

DOCKER_COMPOSE_PATH=${DOCKER_COMPOSE_PATH:-"$SCRIPT_DIR/../../docker-compose.yml"}
NR_DOCKER_COMPOSE_PATH=${NR_DOCKER_COMPOSE_PATH:-"$SCRIPT_DIR/../docker/docker-compose.yml"}
SRC_DIR=${SRC_DIR:-"$SCRIPT_DIR/../../src"} #.env.override

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