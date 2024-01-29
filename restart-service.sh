#!/bin/sh

set -euo pipefail

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# This script is used to build, then restart the newly built service container. It does this by forcing a full stop
# and removal of the container, then recreating it. This is useful for development, as it ensures the latest code
# is running in the container.

if [ -z "$1" ]
then
    echo "Please provide a service name"
    exit 1
fi

docker compose build "$1"
docker compose stop "$1"
docker compose rm --force "$1"
docker compose create "$1"
docker compose start "$1"
