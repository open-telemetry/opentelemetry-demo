#!/bin/bash
# Cleanup script for OpenTelemetry Demo with SQL Server
# This ensures a clean teardown for demos that get built up and torn down often

set -e

echo "🧹 Cleaning up OpenTelemetry Demo..."

# Delete all resources from the main manifest
echo "Deleting deployments, services, and statefulsets..."
kubectl delete -f kubernetes/opentelemetry-demo.yaml --ignore-not-found=true

# Give it a moment to process deletions
sleep 2

# Delete any remaining PVCs (in case retention policy doesn't work)
echo "Cleaning up PVCs..."
kubectl delete pvc --all -n sql --ignore-not-found=true
kubectl delete pvc --all -n otel-demo --ignore-not-found=true

# Optional: Delete namespaces for a complete clean
# Uncomment these lines if you want to remove namespaces too
# echo "Deleting namespaces..."
# kubectl delete namespace sql --ignore-not-found=true
# kubectl delete namespace otel-demo --ignore-not-found=true

echo "✅ Cleanup complete!"
echo ""
echo "To redeploy, run:"
echo "  kubectl apply -f kubernetes/opentelemetry-demo.yaml"
