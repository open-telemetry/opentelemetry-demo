#!/usr/bin/env bash
set -euo pipefail
# Purpose: Update demo applications with the latest upstream changes.
# Notes:
#   This script performs updates for the OpenTelemetry Demo.
# Requirements:
#   - yq: A portable command-line YAML processor.
#   Both can be installed using brew:
#       brew install yq
#
# Example Usage:
#   ./update_demos.sh

# Set default paths if environment variables are not set
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

function update_root_readme {
    ROOT_README_PATH=${ROOT_README_PATH:-"$SCRIPT_DIR/../../README.md"}

    # Download the latest README file from upstream
    curl -sL https://raw.githubusercontent.com/open-telemetry/opentelemetry-demo/main/README.md \
        > "$ROOT_README_PATH"

    # add a section to the root README file with a pointer to New Relic customizations
    SEARCH_VAL="## Quick start"
    REPLACE_VAL='## New Relic customizations\
\
Some customizations have been made to use the demo application for use with\
the New Relic platform, which can be found in the \[newrelic\](\.\/newrelic)\
folder.  See \[this document\](\.\/newrelic\/README.md) for details.\
\
## Quick start'

    sed -i '' "s/${SEARCH_VAL}/${REPLACE_VAL}/g" "$ROOT_README_PATH"

    echo "Completed updating the root README.md file for the OpenTelemetry demo app!"
}

function update_otel_demo_docker {
    DOCKER_COMPOSE_PATH=${DOCKER_COMPOSE_PATH:-"$SCRIPT_DIR/../../docker-compose.yml"}
    NR_DOCKER_COMPOSE_PATH=${NR_DOCKER_COMPOSE_PATH:-"$SCRIPT_DIR/../docker/docker-compose.yml"}
    SRC_DIR=${SRC_DIR:-"$SCRIPT_DIR/../../src"} #.env.override

    # delete any older versions of the NR Docker Compose file
    [ -e "$NR_DOCKER_COMPOSE_PATH" ] && rm "$NR_DOCKER_COMPOSE_PATH"

    # Download the YAML file
    curl -sL https://raw.githubusercontent.com/open-telemetry/opentelemetry-demo/main/docker-compose.yml \
        > "$DOCKER_COMPOSE_PATH"

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
}

function update_otel_demo_k8s_helm {
    NR_HELM_VALUES_PATH=${NR_HELM_VALUES_PATH:-"$SCRIPT_DIR/../k8s/helm/values.yaml"}
    NR_HELM_TEMPLATE_DEST=${NR_HELM_TEMPLATE_DEST:-"$SCRIPT_DIR/../k8s/rendered/manifest.yaml"}

    # delete any older versions of the New Relic helm template manifests
    [ -e "$NR_HELM_TEMPLATE_DEST" ] && rm "$NR_HELM_TEMPLATE_DEST"

    helm template otel-demo open-telemetry/opentelemetry-demo -n opentelemetry-demo --create-namespace -f $NR_HELM_VALUES_PATH > $NR_HELM_TEMPLATE_DEST

    echo "Completed updating the ./k8s/rendered/manifest.yaml for the OpenTelemetry demo app!"
}

# ---- OpenTelemetry Demo Update ----
update_root_readme
update_otel_demo_docker
update_otel_demo_k8s_helm