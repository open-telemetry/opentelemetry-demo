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
helm uninstall --namespace otel-demo-ns --ignore-not-found opentelemetry-demo-postgresql
helm uninstall --namespace otel-demo-ns --ignore-not-found opentelemetry-demo
kubectl delete --namespace otel-demo-ns --ignore-not-found -f postgres-service.yaml
kubectl delete --namespace otel-demo-ns --ignore-not-found -f postgres-service-two-namespaces.yaml

# tear down things installed by deploy-two-namespaces.sh
helm uninstall --namespace otel-demo-ns1 --ignore-not-found opentelemetry-demo-ns1
helm uninstall --namespace otel-demo-ns2 --ignore-not-found opentelemetry-demo-ns2
helm uninstall --namespace otel-demo-ns1 --ignore-not-found opentelemetry-demo-postgresql
kubectl delete --namespace otel-demo-ns1 --ignore-not-found -f postgres-service.yaml
kubectl delete --ignore-not-found -f cross-namespace-service-names.yaml

