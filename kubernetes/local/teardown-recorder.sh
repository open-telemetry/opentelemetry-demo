#!/usr/bin/env bash

set -euo pipefail

cd -P -- "$(dirname -- "$0")"

source utils

if [[ ${1:-} != "no-context-switch" ]]; then
  # If called directly from the shell (and not from deploy.sh etc.), we need to
  # make sure that we work in the local Kubernetes context.
  trap switch_back_to_original_context EXIT
  switch_to_local_context
fi

echo "removing recorder"
helm uninstall --namespace otel-demo --ignore-not-found dash0-load-test-recorder

