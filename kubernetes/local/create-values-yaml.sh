#!/usr/bin/env bash

set -euo pipefail

cd -P -- "$(dirname -- "$0")"

source utils

if [[ -n ${VALUES_YAML:-} ]]; then
  echo "Using custom values yaml file: $VALUES_YAML"
  cp $VALUES_YAML dash0-otel-demo-local-k8s-values.yaml
else
  echo "Creating dash0-otel-demo-local-k8s-values.yaml based on:"
  echo "- $dash0_configuration_dir/demo/environments/aws/demo-eu-west-1-demo.yaml and"
  echo "- $dash0_configuration_dir/demo/values.yaml"
  echo "Set VALUES_YAML to use a custom values file."
  echo
  yq \
    ". *= load(\"$dash0_configuration_dir/demo/environments/aws/demo-eu-west-1-demo.yaml\")" \
    $dash0_configuration_dir/demo/values.yaml | \
    yq --from-file dash0-otel-demo-local-k8s.yq > \
    dash0-otel-demo-local-k8s-values.yaml

  if [[ -n ${OTEL_EXPORTER_OTLP_ENDPOINT:-} ]]; then
    echo "Using non-default reporting endpoint from environment variable"
    echo "OTEL_EXPORTER_OTLP_ENDPOINT: $OTEL_EXPORTER_OTLP_ENDPOINT"
    echo
    yq -i ".opentelemetry-collector.config.exporters.otlp/dash0-dev.endpoint=\"$OTEL_EXPORTER_OTLP_ENDPOINT\" | del(.opentelemetry-collector.config.exporters.otlp/dash0-dev.auth) " dash0-otel-demo-local-k8s-values.yaml
  else
    echo "Reporting to $(yq '.opentelemetry-collector.config.exporters["otlp/dash0-dev"]'.endpoint dash0-otel-demo-local-k8s-values.yaml), set OTEL_EXPORTER_OTLP_ENDPOINT to report somewhere else."
    echo
  fi
fi

