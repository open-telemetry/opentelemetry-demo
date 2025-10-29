#!/bin/bash
# -----------------------------------------------------------------------------
# cleanup-docker.sh
#
# Purpose:
#   Stops and removes all containers and networks created by the OpenTelemetry
#   Demo using Docker Compose.
#
# How to run:
#   ./cleanup-docker.sh
#   (Run from the newrelic/scripts directory)
#
# Dependencies:
#   - Docker
#   - Docker Compose v2+
#   - .env and .env.override files in the project root
# -----------------------------------------------------------------------------
set -euo pipefail

source "$(dirname "$0")/common.sh"
check_tool_installed docker

docker-compose --env-file ../../.env --env-file ../../.env.override --file ../docker/docker-compose.yml down
