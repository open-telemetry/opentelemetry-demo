#!/bin/bash
# -----------------------------------------------------------------------------
# install-docker.sh
#
# Purpose:
#   Installs and starts the OpenTelemetry Demo using Docker Compose.
#
# How to run:
#   ./install-docker.sh
#   (Run from the newrelic/scripts directory)
#
# Dependencies:
#   - Docker
#   - Docker Compose v2+
#   - .env and .env.override files in the project root
#   - NEW_RELIC_LICENSE_KEY (will prompt if not set)
# -----------------------------------------------------------------------------
set -euo pipefail

source "$(dirname "$0")/common.sh"
check_tool_installed docker

prompt_for_license_key

# Run docker compose with comprehensive error handling
if ! docker compose --env-file ../../.env --env-file ../../.env.override --file ../docker/docker-compose.yml up --force-recreate --remove-orphans --detach; then
    echo "Error: Docker Compose deployment failed."
    echo "Possible reasons:"
    echo "  - Environment files not found"
    echo "  - Docker Compose configuration issue"
    echo "  - Insufficient permissions"
    echo "  - Docker daemon not running"
    exit 1
fi
