#!/bin/bash

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo "Error: helm is not installed or not in PATH. Please install helm and try again."
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed or not in PATH. Please install kubectl and try again."
    exit 1
fi

# Prompt the user for input
echo -n "Please enter your New Relic License Key: "
read user_input

# Check if input is empty
if [ -z "$user_input" ]; then
    echo "Error: Empty key. Please enter your New Relic License Key."
    exit 1
fi

# Check if the opentelemetry-demo namespace already exists
if kubectl get ns opentelemetry-demo &> /dev/null; then
    echo "Namespace 'opentelemetry-demo' already exists."
else
    kubectl create ns opentelemetry-demo
fi

kubectl create secret generic newrelic-license-key --from-literal=license-key=$user_input -n opentelemetry-demo

# Check if the open-telemetry repo is already added
if helm repo list | grep -q 'open-telemetry'; then
    echo "Helm repository 'open-telemetry' is already added."
else
    helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
fi

# Update Helm repository
if ! helm repo update open-telemetry; then
    echo "Error: Failed to update open-telemetry Helm repository."
    exit 1
fi

# Install/upgrade OpenTelemetry demo
if ! helm upgrade --install otel-demo open-telemetry/opentelemetry-demo -n opentelemetry-demo -f ../k8s/helm/values.yaml; then
    echo "Error: Failed to install or upgrade OpenTelemetry demo."
    exit 1
fi

echo "OpenTelemetry demo installation completed successfully!"