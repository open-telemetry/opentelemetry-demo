#!/bin/bash

# Script to stitch together Kubernetes manifests from multiple services
# Usage: ./stitch-manifests.sh

set -e

# Define the services to include
# Note: Services without [service-name]-k8s.yaml files will be skipped with a warning
SERVICES=(
    "accounting"
    "ad"
    "astronomy-loadgen"
    "cart"
    "checkout"
    "currency"
    "email"
    "flagd"
    "flagd-config"
    "flagd-ui"
    "fraud-detection"
    "frontend"
    "frontend-proxy"
    "image-provider"
    "kafka"
    "llm"
    "load-generator"
    "opentelemetry-demo"
    "otel-demo"
    "payment"
    "postgres"
    "product-catalog"
    "product-catalog-products"
    "product-reviews"
    "quote"
    "react-native-app"
    "recommendation"
    "setup-sql"
    "shipping"
    "shop-dc-shim"
    "sql"
    "sql-server-fraud"
    "thousandeyes"
    "valkey-cart"
)

# Get version from SPLUNK-VERSION file
VERSION=$(cat SPLUNK-VERSION)
echo "Creating manifest for version: $VERSION"

# Output directory and file
OUTPUT_DIR="kubernetes"
OUTPUT_FILE="$OUTPUT_DIR/splunk-astronomy-shop-${VERSION}.yaml"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Create header for the combined manifest
cat > "$OUTPUT_FILE" << EOF
# Splunk Astronomy Shop Kubernetes Manifest
# Version: $VERSION
# Generated on: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# This manifest combines all service deployments for the Splunk Astronomy Shop
---
EOF

# Counter for found manifests
FOUND=0
MISSING=()

# Loop through each service and append its manifest
for SERVICE in "${SERVICES[@]}"; do
    MANIFEST_FILE="src/${SERVICE}/${SERVICE}-k8s.yaml"

    if [ -f "$MANIFEST_FILE" ]; then
        echo "Adding manifest for: $SERVICE"
        echo "" >> "$OUTPUT_FILE"
        echo "# === $SERVICE ===" >> "$OUTPUT_FILE"
        cat "$MANIFEST_FILE" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        echo "---" >> "$OUTPUT_FILE"
        FOUND=$((FOUND + 1))
    else
        echo "Warning: Manifest not found for $SERVICE at $MANIFEST_FILE"
        MISSING+=("$SERVICE")
    fi
done

# Summary
echo ""
echo "=========================================="
echo "Manifest stitching complete!"
echo "=========================================="
echo "Version: $VERSION"
echo "Output file: $OUTPUT_FILE"
echo "Services found: $FOUND"
echo "Services missing: ${#MISSING[@]}"

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo "Missing manifests for:"
    for SERVICE in "${MISSING[@]}"; do
        echo "  - $SERVICE"
    done
fi

echo ""
echo "To customize the service list, edit the SERVICES array in this script."
