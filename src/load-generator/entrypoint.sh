#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# See ../README.md#controlling-traffic-and-concurrency-via-feature-flags for
# why this wrapper polls flagd and restarts k6 on VU changes instead of
# resizing VUs in place, and why K6_DURATION must not be passed alongside
# K6_VUS/K6_BROWSER_VUS.

set -u

FLAGD_HOST="${FLAGD_HOST:-flagd}"
FLAGD_OFREP_PORT="${FLAGD_OFREP_PORT:-8016}"
DEFAULT_VUS="${K6_VUS:-10}"
DEFAULT_BROWSER_VUS="${K6_BROWSER_VUS:-1}"
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
# given default if flagd is unreachable or returns a non-numeric value. Pass
# allow_zero as the third argument for flags where 0 is a meaningful value
# (loadGeneratorBrowserVUs uses 0 to disable the browser scenario); otherwise 0
# is treated as unreachable and falls back to the default.
# Usage: fetch_flag <flag_name> <default_value> [allow_zero]
fetch_flag() {
  value=$(wget -qO- --post-data='{}' --header='Content-Type: application/json' \
    "http://${FLAGD_HOST}:${FLAGD_OFREP_PORT}/ofrep/v1/evaluate/flags/$1" 2>/dev/null \
    | grep -o '"value":[0-9]*' | cut -d: -f2)
  case "$value" in
    ''|*[!0-9]*) echo "$2" ;;
    0)
      if [ "${3:-}" = "allow_zero" ]; then
        echo 0
      else
        echo "$2"
      fi
      ;;
    *) echo "$value" ;;
  esac
}

current_vus=$(fetch_flag loadGeneratorVUs "$DEFAULT_VUS")
current_browser_vus=$(fetch_flag loadGeneratorBrowserVUs "$DEFAULT_BROWSER_VUS" allow_zero)

while [ "$running" -eq 1 ]; do
  echo "entrypoint.sh: starting k6 with K6_VUS=${current_vus} K6_BROWSER_VUS=${current_browser_vus}"
  K6_VUS="$current_vus" K6_BROWSER_VUS="$current_browser_vus" k6 run script.js --out opentelemetry &
  child=$!

  while [ "$running" -eq 1 ] && kill -0 "$child" 2>/dev/null; do
    sleep "$POLL_INTERVAL_SECONDS"
    # Fall back to the last successfully evaluated value (not DEFAULT_*) so a
    # transient flagd outage doesn't look like a flag change and restart k6.
    new_vus=$(fetch_flag loadGeneratorVUs "$current_vus")
    new_browser_vus=$(fetch_flag loadGeneratorBrowserVUs "$current_browser_vus" allow_zero)
    if [ "$new_vus" != "$current_vus" ] || [ "$new_browser_vus" != "$current_browser_vus" ]; then
      echo "entrypoint.sh: VU flags changed (VUs ${current_vus} -> ${new_vus}, browser VUs ${current_browser_vus} -> ${new_browser_vus}), restarting k6"
      current_vus="$new_vus"
      current_browser_vus="$new_browser_vus"
      kill -TERM "$child" 2>/dev/null || true
      break
    fi
  done

  wait "$child" 2>/dev/null
done
