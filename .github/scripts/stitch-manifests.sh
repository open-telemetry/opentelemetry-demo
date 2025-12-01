#!/bin/bash

# Script to stitch together Kubernetes manifests from multiple services
# Usage: ./stitch-manifests.sh [registry_env]
#   registry_env: Optional - 'dev' or 'prod' to use registry from services.yaml
#                 If not specified, uses original registry URLs from manifests
#
# This script reads service configuration from services.yaml
# To add a new service, edit services.yaml instead of this script

set -e

# Parse optional registry environment argument
REGISTRY_ENV="${1:-}"

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

# Get registry URL if registry environment is specified
REGISTRY_URL=""
if [ -n "$REGISTRY_ENV" ]; then
    if command -v python3 &> /dev/null; then
        REGISTRY_URL=$(python3 -c "import yaml; config = yaml.safe_load(open('services.yaml')); print(config.get('registry', {}).get('$REGISTRY_ENV', ''))" 2>/dev/null || echo "")
        if [ -n "$REGISTRY_URL" ]; then
            echo "Using registry environment: $REGISTRY_ENV"
            echo "Registry URL: $REGISTRY_URL"
        else
            echo "Warning: Registry environment '$REGISTRY_ENV' not found in services.yaml, using default"
        fi
    fi
fi

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
        # Check if service has replace_registry flag set to false
        SHOULD_REPLACE="true"
        if [ -n "$REGISTRY_URL" ] && command -v python3 &> /dev/null; then
            SHOULD_REPLACE=$(python3 -c "
import yaml
config = yaml.safe_load(open('services.yaml'))
for svc in config.get('services', []):
    if svc.get('name') == '$SERVICE':
        print(str(svc.get('replace_registry', True)).lower())
        break
" 2>/dev/null || echo "true")
        fi

        echo "Adding manifest for: $SERVICE"
        echo "" >> "$OUTPUT_FILE"
        echo "# === $SERVICE ===" >> "$OUTPUT_FILE"

        # Process manifest: replace registry URLs (if needed) and version numbers
        if [ -n "$REGISTRY_URL" ] && [ "$SHOULD_REPLACE" = "true" ]; then
            # Replace registry URLs, image tags, and version numbers
            # Pattern matches: ghcr.io/{org}/{repo} and replaces with ${REGISTRY_URL}
            # Preserves: /otel-{service} part but replaces :{tag} with :${VERSION}
            sed -e "s|ghcr.io/[^/]*/[^/]*|${REGISTRY_URL}|g" \
                -e "/image:/s|:[0-9][0-9.][^[:space:]]*|:${VERSION}|" \
                -e "s|app.kubernetes.io/version: [0-9][0-9.]*|app.kubernetes.io/version: ${VERSION}|g" \
                -e "s|service.version=[0-9][0-9.]*|service.version=${VERSION}|g" \
                "$MANIFEST_FILE" >> "$OUTPUT_FILE"
        else
            # Replace only version numbers in labels (keep original registry and image tags)
            sed -e "s|app.kubernetes.io/version: [0-9][0-9.]*|app.kubernetes.io/version: ${VERSION}|g" \
                -e "s|service.version=[0-9][0-9.]*|service.version=${VERSION}|g" \
                "$MANIFEST_FILE" >> "$OUTPUT_FILE"
            if [ -n "$REGISTRY_URL" ] && [ "$SHOULD_REPLACE" = "false" ]; then
                echo "  (using original registry)"
            fi
        fi

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
if [ -n "$REGISTRY_URL" ]; then
    echo "Registry: $REGISTRY_URL ($REGISTRY_ENV)"
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo "Missing manifests for:"
    for SERVICE in "${MISSING[@]}"; do
        echo "  - $SERVICE"
    done
fi

echo ""
echo "To add a new service, edit services.yaml in the repository root."
