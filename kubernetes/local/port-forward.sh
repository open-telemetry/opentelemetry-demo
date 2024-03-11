#!/usr/bin/env bash

set -euo pipefail

kubectl port-forward --namespace otel-demo-ns service/opentelemetry-demo-frontendproxy 8080:8080

