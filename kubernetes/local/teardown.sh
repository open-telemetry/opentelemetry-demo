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

# tear down things installed by deploy.sh
echo Removing PostgreSQL
helm uninstall --namespace otel-demo --ignore-not-found opentelemetry-demo-postgresql
echo Removing OpenTelemetry Demo
helm uninstall --namespace otel-demo --ignore-not-found opentelemetry-demo
echo Removing PostgreSQL Service
kubectl delete --namespace otel-demo --ignore-not-found -f postgres-service.yaml

if [[ -n ${WITH_RECORDER:-} ]]; then
  ./teardown-recorder.sh no-context-switch
fi

