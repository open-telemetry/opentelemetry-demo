#!/usr/bin/env bash

set -euo pipefail

cd -P -- "$(dirname -- "$0")"

pwd

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

