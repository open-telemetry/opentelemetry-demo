#!/usr/bin/env bash

set -euo pipefail
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

log() { echo "$1" >&2; }

while IFS= read -d $'\0' -r dir; do
    svcname="$(basename "${dir}")"
    log "Killing: ${svcname}"
    docker kill "${svcname}" || true
    
done < <(find "${SCRIPTDIR}/../src" -mindepth 1 -maxdepth 1 -type d -print0)

log "Killing: redis-cart"
docker kill redis-cart || true

log "Killing: jaeger"
docker kill jaeger || true
