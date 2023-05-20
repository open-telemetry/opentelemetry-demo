#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


# This script is used to stop the demo.
# This will stop the full demo which contains all components from the demo itself and remove all orphans and volumes to
# ensure a clean state.

echo "Stopping demo..."
docker compose -f docker-compose.full.yml down --remove-orphans --volumes
echo "Demo stopped."
