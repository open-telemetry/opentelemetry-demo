#!/usr/bin/env bash
set -euo pipefail

docker compose \
  --env-file .env \
  --env-file .env.override \
  -f compose.yaml \
  -f compose.full.yaml \
  -f compose.observability.yaml \
  -f compose.extras.yaml \
  -f compose.oncall.yaml \
  up -d --build oncall
