#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# k6's constant-vus executor can't resize its VU pool at runtime - k6 v2
# dropped the externally-controlled executor, and its REST API now rejects
# live VU changes outright ("live VU configuration updates are not
# supported"). To make the loadGeneratorVUs feature flag take effect without
# operator intervention, this wrapper polls flagd and restarts k6 with a new
# K6_VUS only when the flag's value actually changes, rather than on a fixed
# timer.
#
# Do not also pass K6_DURATION through as a container env var alongside
# K6_VUS: k6 auto-maps K6_-prefixed env vars to its global CLI flags, and
# having both set at once makes k6 discard the script's `scenarios` config
# entirely in favor of a single implicit "default" scenario.

set -u

FLAGD_HOST="${FLAGD_HOST:-flagd}"
FLAGD_OFREP_PORT="${FLAGD_OFREP_PORT:-8016}"
DEFAULT_VUS="${K6_VUS:-10}"
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

# Reads the loadGeneratorVUs flag via flagd's OFREP endpoint, falling back to
# DEFAULT_VUS if flagd is unreachable or returns a non-positive value.
fetch_vus() {
  value=$(wget -qO- --post-data='{}' --header='Content-Type: application/json' \
    "http://${FLAGD_HOST}:${FLAGD_OFREP_PORT}/ofrep/v1/evaluate/flags/loadGeneratorVUs" 2>/dev/null \
    | grep -o '"value":[0-9]*' | cut -d: -f2)
  case "$value" in
    ''|*[!0-9]*) echo "$DEFAULT_VUS" ;;
    0) echo "$DEFAULT_VUS" ;;
    *) echo "$value" ;;
  esac
}

current_vus=$(fetch_vus)

while [ "$running" -eq 1 ]; do
  echo "entrypoint.sh: starting k6 with K6_VUS=${current_vus}"
  K6_VUS="$current_vus" k6 run script.js --out opentelemetry &
  child=$!

  while [ "$running" -eq 1 ] && kill -0 "$child" 2>/dev/null; do
    sleep "$POLL_INTERVAL_SECONDS"
    new_vus=$(fetch_vus)
    if [ "$new_vus" != "$current_vus" ]; then
      echo "entrypoint.sh: loadGeneratorVUs changed ${current_vus} -> ${new_vus}, restarting k6"
      current_vus="$new_vus"
      kill -TERM "$child" 2>/dev/null || true
      break
    fi
  done

  wait "$child" 2>/dev/null
done
