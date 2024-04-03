#!/usr/bin/env bash

# SPDX-FileCopyrightText: Copyright 2024 Dash0 Inc.

set -euo pipefail

cd -P -- "$(dirname -- "$0")"

source utils

if [[ ${1:-} != "no-context-switch" ]]; then
  # If called directly from the shell (and not from deploy.sh etc.), we need to
  # make sure that we work in the local Kubernetes context.
  trap switch_back_to_original_context EXIT
  switch_to_local_context
fi

refresh_image_pull_secret otel-demo

# remove previous deployment, if it exists
./teardown-recorder.sh no-context-switch

sleep 5

LOCAL_DATA_DIR=$HOME/data
mkdir -p $LOCAL_DATA_DIR

yq -i ".extraVolumes[0].hostPath.path=\"$LOCAL_DATA_DIR\"" deploy-recorder.yaml

echo "deploying recorder"
helm install \
  --namespace otel-demo \
  --create-namespace \
  dash0-load-test-recorder \
  open-telemetry/opentelemetry-collector \
  --values deploy-recorder.yaml

