#!/usr/bin/env bash

set -euo pipefail

cd -P -- "$(dirname -- "$0")"

source utils

git_pull_dash0_configuration

trap switch_back_to_original_context EXIT
switch_to_local_context

refresh_image_pull_secret otel-demo

./teardown.sh no-context-switch

sleep 5

./create-values-yaml.sh $dash0_configuration_dir

helm install --namespace otel-demo --create-namespace opentelemetry-demo-postgresql oci://registry-1.docker.io/bitnamicharts/postgresql --values postgres-values.yaml
helm install \
  --namespace otel-demo \
  --create-namespace \
  opentelemetry-demo \
  open-telemetry/opentelemetry-demo  \
  --values dash0-otel-demo-local-k8s-values.yaml
kubectl apply --namespace otel-demo -f postgres-service.yaml

kubectl cp ../../src/ffspostgres/init-scripts/10-ffs_schema.sql --namespace otel-demo opentelemetry-demo-postgresql-0:/tmp/
kubectl cp ../../src/ffspostgres/init-scripts/20-ffs_data.sql --namespace otel-demo opentelemetry-demo-postgresql-0:/tmp/
kubectl exec --namespace otel-demo opentelemetry-demo-postgresql-0 -- psql postgresql://ffs:ffs@localhost/ffs -a -f /tmp/10-ffs_schema.sql
kubectl exec --namespace otel-demo opentelemetry-demo-postgresql-0 -- psql postgresql://ffs:ffs@localhost/ffs -a -f /tmp/20-ffs_data.sql

echo waiting for the frontend and frontendproxy pod to become ready
sleep 5
kubectl wait --namespace otel-demo --for=condition=ready pod -l app.kubernetes.io/component=frontendproxy --timeout 10s
kubectl wait --namespace otel-demo --for=condition=ready pod -l app.kubernetes.io/component=frontend --timeout 20s
./port-forward.sh

