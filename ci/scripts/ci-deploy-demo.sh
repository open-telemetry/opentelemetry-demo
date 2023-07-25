#!/usr/bin/env bash

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# This script is used to deploy collector on demo account cluster

set -euo pipefail
IFS=$'\n\t'
set -x

clusterName=$1
clusterArn=$2
region=$3
namespace=$4

install_demo() {
  # Set the namespace and release name
  release_name="opentelemetry-demo"

  # Deploy zookeeper which is not a default component.
  kubectl apply -f ./src/zookeeperservice/deployment.yaml -n "${namespace}"

  # if repo already exists, helm 3+ will skip
  helm --debug repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts

  # --install will run `helm install` if not already present.
  helm --debug upgrade "${release_name}" -n "${namespace}" open-telemetry/opentelemetry-demo --install \
    -f ./ci/values.yaml \
    --set-string default.image.tag="v$CI_COMMIT_SHORT_SHA"
  
  # Deploy java order producer which is not a default component.
  sed -i "s/PLACEHOLDER_COMMIT_SHA/v$CI_COMMIT_SHORT_SHA/g" ./src/orderproducerservice/deployment.yaml
  kubectl apply -f ./src/orderproducerservice/deployment.yaml -n "${namespace}"
}

###########################################################################################################

aws eks --region "${region}" update-kubeconfig --name "${clusterName}"
kubectl config use-context "${clusterArn}"

install_demo
