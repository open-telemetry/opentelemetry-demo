#!/usr/bin/env bash

set -euo pipefail

cd -P -- "$(dirname -- "$0")"

source utils

git_pull_dash0_configuration

trap switch_back_to_original_context EXIT
switch_to_local_context

refresh_image_pull_secret otel-demo-ns1 otel-demo-ns2

./teardown.sh no-context-switch

sleep 5

yq \
  ". *= load(\"$dash0_configuration_dir/demo/environments/aws/demo-eu-west-1-demo.yaml\")" \
  $dash0_configuration_dir/demo/values.yaml | \
  yq --from-file ns1.yq > \
  ns1-values.yaml
yq \
  ". *= load(\"$dash0_configuration_dir/demo/environments/aws/demo-eu-west-1-demo.yaml\")" \
  $dash0_configuration_dir/demo/values.yaml | \
  yq --from-file ns2.yq > \
  ns2-values.yaml

helm install --namespace otel-demo-ns1 --create-namespace opentelemetry-demo-postgresql oci://registry-1.docker.io/bitnamicharts/postgresql --values postgres-values.yaml
helm install --namespace otel-demo-ns1 --create-namespace opentelemetry-demo-ns1 open-telemetry/opentelemetry-demo --values ns1-values.yaml
helm install --namespace otel-demo-ns2 --create-namespace opentelemetry-demo-ns2 open-telemetry/opentelemetry-demo --values ns2-values.yaml
kubectl apply -f cross-namespace-service-names.yaml
kubectl apply --namespace otel-demo-ns1 -f postgres-service-two-namespaces.yaml

kubectl cp ../../src/ffspostgres/init-scripts/10-ffs_schema.sql --namespace otel-demo-ns1 opentelemetry-demo-postgresql-0:/tmp/
kubectl cp ../../src/ffspostgres/init-scripts/20-ffs_data.sql --namespace otel-demo-ns1 opentelemetry-demo-postgresql-0:/tmp/
kubectl exec --namespace otel-demo-ns1 opentelemetry-demo-postgresql-0 -- psql postgresql://ffs:ffs@localhost/ffs -a -f /tmp/10-ffs_schema.sql
kubectl exec --namespace otel-demo-ns1 opentelemetry-demo-postgresql-0 -- psql postgresql://ffs:ffs@localhost/ffs -a -f /tmp/20-ffs_data.sql

echo waiting for the frontend and frontendproxy pod to become ready
sleep 5
kubectl wait --namespace otel-demo-ns-1 --for=condition=ready pod -l app.kubernetes.io/component=frontendproxy --timeout 10s
kubectl wait --namespace otel-demo-ns-1 --for=condition=ready pod -l app.kubernetes.io/component=frontend --timeout 20s
./port-forward-two-ns.sh

