#!/usr/bin/env bash

set -euo pipefail

kubectl port-forward --namespace otel-demo-ns1 service/opentelemetry-demo-ns1-frontendproxy 8080:8080

