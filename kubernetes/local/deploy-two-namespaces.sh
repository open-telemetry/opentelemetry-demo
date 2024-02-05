#!/usr/bin/env bash

set -euo pipefail

cd -P -- "$(dirname -- "$0")"

./teardown.sh

sleep 5

yq --from-file ns1.yq ../../../dash0-configuration/demo/environments/aws/demo-eu-west-1-demo.yaml > ns1-values.yaml
yq --from-file ns2.yq ../../../dash0-configuration/demo/environments/aws/demo-eu-west-1-demo.yaml > ns2-values.yaml

helm install --namespace otel-demo-ns1 --create-namespace opentelemetry-demo-postgresql oci://registry-1.docker.io/bitnamicharts/postgresql --values postgres-values.yaml
helm install --namespace otel-demo-ns1 --create-namespace opentelemetry-demo-ns1 open-telemetry/opentelemetry-demo --values ns1-values.yaml
helm install --namespace otel-demo-ns2 --create-namespace opentelemetry-demo-ns2 open-telemetry/opentelemetry-demo --values ns2-values.yaml
kubectl apply -f cross-namespace-service-names.yaml
kubectl apply --namespace otel-demo-ns1 -f postgres-service-two-namespaces.yaml

kubectl cp ../../src/ffspostgres/init-scripts/10-ffs_schema.sql --namespace otel-demo-ns1 opentelemetry-demo-postgresql-0:/tmp/
kubectl cp ../../src/ffspostgres/init-scripts/20-ffs_data.sql --namespace otel-demo-ns1 opentelemetry-demo-postgresql-0:/tmp/
kubectl exec --namespace otel-demo-ns1 opentelemetry-demo-postgresql-0 -- psql postgresql://ffs:ffs@localhost/ffs -a -f /tmp/10-ffs_schema.sql
kubectl exec --namespace otel-demo-ns1 opentelemetry-demo-postgresql-0 -- psql postgresql://ffs:ffs@localhost/ffs -a -f /tmp/20-ffs_data.sql

kubectl port-forward --namespace otel-demo-ns1 service/opentelemetry-demo-ns1-frontendproxy 8080:8080

