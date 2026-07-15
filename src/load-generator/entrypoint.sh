#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# See ../README.md#controlling-traffic-and-concurrency-via-feature-flags for
# why this wrapper polls flagd and restarts k6 when the VU count changes
# instead of resizing VUs in place, and why the count is passed to k6 as
# LOAD_GENERATOR_VUS rather than K6_VUS/K6_DURATION.

set -u

FLAGD_HOST="${FLAGD_HOST:-flagd}"
FLAGD_OFREP_PORT="${FLAGD_OFREP_PORT:-8016}"
DEFAULT_VUS="${LOAD_GENERATOR_VUS:-10}"
POLL_INTERVAL_SECONDS=10

running=1
child=""

on_term() {
  running=0
  if [ -n "$child" ]; then
    kill -TERM "$child" 2>/dev/null || true
  fi
}
trap on_term TERM INT

# Reads an integer feature flag via flagd's OFREP endpoint, falling back to the
# given default if flagd is unreachable or returns a non-numeric value.
# Usage: fetch_flag <flag_name> <default_value>
fetch_flag() {
  value=$(wget -qO- --post-data='{}' --header='Content-Type: application/json' \
    "http://${FLAGD_HOST}:${FLAGD_OFREP_PORT}/ofrep/v1/evaluate/flags/$1" 2>/dev/null \
    | grep -o '"value":[0-9]*' | cut -d: -f2)
  case "$value" in
    ''|*[!0-9]*|0) echo "$2" ;;
    *) echo "$value" ;;
  esac
}

current_vus=$(fetch_flag loadGeneratorVUs "$DEFAULT_VUS")

while [ "$running" -eq 1 ]; do
  echo "entrypoint.sh: starting k6 with LOAD_GENERATOR_VUS=${current_vus}"
  LOAD_GENERATOR_VUS="$current_vus" k6 run script.js --out opentelemetry &
  child=$!

  while [ "$running" -eq 1 ] && kill -0 "$child" 2>/dev/null; do
    sleep "$POLL_INTERVAL_SECONDS"
    # Fall back to the last successfully evaluated value (not DEFAULT_VUS) so a
    # transient flagd outage doesn't look like a flag change and restart k6.
    new_vus=$(fetch_flag loadGeneratorVUs "$current_vus")
    if [ "$new_vus" != "$current_vus" ]; then
      echo "entrypoint.sh: VU flag changed (${current_vus} -> ${new_vus}), restarting k6"
      current_vus="$new_vus"
      kill -TERM "$child" 2>/dev/null || true
      break
    fi
  done

  wait "$child" 2>/dev/null
done
