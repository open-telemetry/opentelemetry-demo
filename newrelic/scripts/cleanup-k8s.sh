#!/bin/bash

release_name=otel-demo
namespace=opentelemetry-demo

# Check if the Helm release exists
if helm status "$release_name" -n $namespace &> /dev/null; then
    echo "Helm release '$release_name' found. Uninstalling..."
    helm uninstall "$release_name" -n $namespace
    if [ $? -eq 0 ]; then
        echo "Successfully uninstalled '$release_name'"
    else
        echo "Failed to uninstall '$release_name'"
        exit 1
    fi
else
    echo "Helm release '$release_name' not found."
fi

# Check if namespace exists
if kubectl get namespace "$namespace" &> /dev/null; then
    echo "Namespace '$namespace' found. Deleting..."
    kubectl delete namespace "$namespace"
    if [ $? -eq 0 ]; then
        echo "Successfully deleted namespace '$namespace'"
    else
        echo "Failed to delete namespace '$namespace'"
        exit 1
    fi
else
    echo "Namespace '$namespace' not found."
fi

exit 0