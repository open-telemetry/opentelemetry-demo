#!/bin/bash

# Script to stitch together Kubernetes manifests from multiple services
# Usage: ./stitch-manifests.sh
#
# This script reads service configuration from services.yaml
# To add a new service, edit services.yaml instead of this script

set -e

# Get version from SPLUNK-VERSION file
VERSION=$(cat SPLUNK-VERSION)
echo "Creating manifest for version: $VERSION"

# Load services from services.yaml
echo "Reading services from services.yaml..."
if command -v python3 &> /dev/null; then
    # Use Python helper to parse YAML
    SERVICES_LIST=$(python3 .github/scripts/get-services.py --manifest)
    if [ $? -ne 0 ]; then
        echo "Error: Failed to read services.yaml"
        exit 1
    fi
    # Convert space-separated list to array
    read -ra SERVICES <<< "$SERVICES_LIST"
else
    echo "Error: python3 is required to parse services.yaml"
    echo "Please install Python 3 or manually update the SERVICES array in this script"
    exit 1
fi

echo "Found ${#SERVICES[@]} services configured for manifest inclusion"

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
# Services are defined in services.yaml
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
echo "To add a new service, edit services.yaml in the repository root."
