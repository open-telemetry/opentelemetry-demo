#!/usr/bin/env bash
set -euo pipefail

docker compose -f compose.oncall.yaml exec oncall /bin/bash
