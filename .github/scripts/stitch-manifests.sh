#!/bin/bash

# Script to stitch together Kubernetes manifests from multiple services
# Usage: ./stitch-manifests.sh [registry_env] [diab] [output_dir] [suffix]
#   registry_env: Optional - 'dev' or 'prod' to use registry from services.yaml
#                 If not specified, uses original registry URLs from manifests
#   diab: Optional - 'diab' to enable DIAB scenario (includes ingress, adds -diab suffix)
#   output_dir: Optional - output directory (default: kubernetes)
#   suffix: Optional - additional suffix to add before .yaml (e.g., '-beta')
#
# This script reads service configuration from services.yaml
# Services with a 'group' field are stitched into separate manifests:
#   - No group    → main manifest (splunk-astronomy-shop-X.X.X.yaml)
#   - group: lambda  → splunk-astronomy-shop-X.X.X-lambda.yaml
#   - group: dc-shim → splunk-astronomy-shop-X.X.X-dc-shim.yaml
#
# To add a new service, edit services.yaml instead of this script

set -e
IFS=$' \t\n'

# Parse optional arguments
REGISTRY_ENV="${1:-}"
DIAB_SCENARIO="${2:-}"
OUTPUT_DIR_ARG="${3:-}"
EXTRA_SUFFIX="${4:-}"

# Get version from SPLUNK-VERSION file
VERSION=$(cat SPLUNK-VERSION)
echo "Creating manifest for version: $VERSION"

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

# Output directory
OUTPUT_DIR="${OUTPUT_DIR_ARG:-kubernetes}"
mkdir -p "$OUTPUT_DIR"

# ============================================================
# Function: get_service_version
# Get the version for a specific service
# Priority: .hotfix.yaml > .service-versions.yaml > VERSION
# ============================================================
get_service_version() {
    local SERVICE="$1"
    local SVC_VERSION="${VERSION}"

    # Check for hotfix first (production hotfixes)
    if command -v python3 &> /dev/null && [ -f ".github/scripts/manage-hotfix.py" ]; then
        local HOTFIX_VERSION
        HOTFIX_VERSION=$(python3 .github/scripts/manage-hotfix.py get "$SERVICE" 2>/dev/null || echo "")
        if [ -n "$HOTFIX_VERSION" ] && [ "$HOTFIX_VERSION" != "$VERSION" ]; then
            SVC_VERSION="$HOTFIX_VERSION"
        fi
    fi

    # Check for per-service version (test/dev builds)
    if [ "$SVC_VERSION" == "$VERSION" ] && command -v python3 &> /dev/null && [ -f ".github/scripts/get-service-version.py" ]; then
        SVC_VERSION=$(python3 .github/scripts/get-service-version.py "$SERVICE" "$VERSION")
    fi

    echo "$SVC_VERSION"
}

# ============================================================
# Function: should_replace_registry
# Check if a service should have its registry URL replaced
# ============================================================
should_replace_registry() {
    local SERVICE="$1"
    if [ -n "$REGISTRY_URL" ] && command -v python3 &> /dev/null; then
        python3 -c "
import yaml
config = yaml.safe_load(open('services.yaml'))
for svc in config.get('services', []):
    if svc.get('name') == '$SERVICE':
        print(str(svc.get('replace_registry', True)).lower())
        break
" 2>/dev/null || echo "true"
    else
        echo "true"
    fi
}

# ============================================================
# Function: get_manifest_file
# Read services.yaml for optional manifest_file override
# ============================================================
get_manifest_file() {
    local SERVICE="$1"
    if command -v python3 &> /dev/null; then
        python3 -c "
import yaml
config = yaml.safe_load(open('services.yaml'))
for svc in config.get('services', []):
    if svc.get('name') == '$SERVICE':
        print(svc.get('manifest_file', 'src/${SERVICE}/${SERVICE}-k8s.yaml'))
        break
" 2>/dev/null || echo "src/${SERVICE}/${SERVICE}-k8s.yaml"
    else
        echo "src/${SERVICE}/${SERVICE}-k8s.yaml"
    fi
}

# ============================================================
# Function: stitch_service
# Append a single service manifest to an output file.
# Dedupes: if multiple svcs share the same manifest_file, only the first
# call emits it (tracked via STITCHED_MANIFESTS assoc array).
# ============================================================
declare -A STITCHED_MANIFESTS
stitch_service() {
    local SERVICE="$1"
    local OUT_FILE="$2"
    local MANIFEST_FILE
    MANIFEST_FILE=$(get_manifest_file "$SERVICE")

    if [ ! -f "$MANIFEST_FILE" ]; then
        echo "Warning: Manifest not found for $SERVICE at $MANIFEST_FILE"
        return 1
    fi

    # Dedupe by manifest path + output file so shared manifests
    # (e.g. secureapp-loadgen-{java,node,python}) emit only once.
    local DEDUPE_KEY="${OUT_FILE}::${MANIFEST_FILE}"
    if [ "${STITCHED_MANIFESTS[$DEDUPE_KEY]:-}" = "1" ]; then
        echo "Skipping $SERVICE — manifest $MANIFEST_FILE already stitched into $OUT_FILE"
        return 0
    fi
    STITCHED_MANIFESTS[$DEDUPE_KEY]=1

    local SERVICE_VERSION
    SERVICE_VERSION=$(get_service_version "$SERVICE")
    local SHOULD_REPLACE
    SHOULD_REPLACE=$(should_replace_registry "$SERVICE")

    echo "Adding manifest for: $SERVICE (version: $SERVICE_VERSION)"
    echo "" >> "$OUT_FILE"
    echo "# === $SERVICE ===" >> "$OUT_FILE"

    # Process manifest: replace registry URLs (if needed) and version numbers
    # Version regex: match semver (digits+dots) plus any suffix (-beta, -hotfix-*, etc.)
    # The full tag is replaced wholesale by SERVICE_VERSION — no trailing capture group,
    # which previously caused double-suffix bugs (e.g., 2.0.1-beta-beta).
    if [ -n "$REGISTRY_URL" ] && [ "$SHOULD_REPLACE" = "true" ]; then
        # Registry + pod-level version labels use the pod's SERVICE_VERSION;
        # image tags are set per-image (apply_image_versions) so embedded
        # sidecar images keep their own service version.
        local TMP; TMP=$(mktemp)
        sed -e "s|ghcr.io/[^/]*/[^/]*|${REGISTRY_URL}|g" \
            -e "s|app.kubernetes.io/version: [0-9][0-9.]*[^\"[:space:]]*|app.kubernetes.io/version: ${SERVICE_VERSION}|g" \
            -e "s|service.version=[0-9][0-9.]*[^,[:space:]]*|service.version=${SERVICE_VERSION}|g" \
            "$MANIFEST_FILE" > "$TMP"
        apply_image_versions "$TMP"
        cat "$TMP" >> "$OUT_FILE"
        rm -f "$TMP"
    elif [ "$SHOULD_REPLACE" = "false" ]; then
        cat "$MANIFEST_FILE" >> "$OUT_FILE"
        echo "  (using original registry and versions)"
    else
        sed -e "s|app.kubernetes.io/version: [0-9][0-9.]*[^\"[:space:]]*|app.kubernetes.io/version: ${SERVICE_VERSION}|g" \
            -e "s|service.version=[0-9][0-9.]*[^,[:space:]]*|service.version=${SERVICE_VERSION}|g" \
            "$MANIFEST_FILE" >> "$OUT_FILE"
    fi

    echo "" >> "$OUT_FILE"
    echo "---" >> "$OUT_FILE"
    return 0
}

# ============================================================
# Function: apply_image_versions
# Retag each image line by the version of the service that image
# belongs to (image name is otel-<service>). This ensures sidecar
# images embedded in another pod's manifest (e.g. secureapp-loadgen-*
# inside recommendation-k8s.yaml) get their OWN service version rather
# than the host pod's — otherwise a single-service build retags the
# sidecar to a tag that was never built (ImagePullBackOff).
# Operates in place on an already registry-normalized file.
# ============================================================
apply_image_versions() {
    local FILE="$1"
    local IMG NAME V
    for IMG in $(grep -oE "${REGISTRY_URL}/otel-[A-Za-z0-9._-]+:[0-9][0-9.]*[^[:space:]]*" "$FILE" \
                 | sed -E 's|:[0-9].*$||' | sort -u); do
        NAME="${IMG##*/otel-}"
        V=$(get_service_version "$NAME")
        # Escape regex-significant chars in the image path for the LHS.
        local IMG_RE
        IMG_RE=$(printf '%s' "$IMG" | sed -e 's/[.[\*^$/]/\\&/g')
        sed -i.bak "s|\(${IMG_RE}\):[0-9][0-9.]*[^[:space:]]*|\1:${V}|g" "$FILE"
        rm -f "${FILE}.bak"
    done
}

# ============================================================
# Function: stitch_payment
# Special handling for payment A/B testing variants
# ============================================================
stitch_payment() {
    local OUT_FILE="$1"
    local VARIANT_A="src/payment/payment-vA-k8s.yaml"
    local VARIANT_B="src/payment/payment-vB-k8s.yaml"
    local FOUND_COUNT=0

    local SERVICE_VERSION
    SERVICE_VERSION=$(get_service_version "payment")
    local SHOULD_REPLACE
    SHOULD_REPLACE=$(should_replace_registry "payment")

    # Determine which manifests to use
    local MANIFESTS=()
    local LABELS=()
    if [ -f "$VARIANT_A" ] && [ -f "$VARIANT_B" ]; then
        echo "Payment service: Using A/B testing variants (vA and vB)"
        MANIFESTS=("$VARIANT_A" "$VARIANT_B")
        LABELS=("payment-vA" "payment-vB")
    else
        MANIFESTS=("src/payment/payment-k8s.yaml")
        LABELS=("payment")
    fi

    for i in "${!MANIFESTS[@]}"; do
        local CURRENT_MANIFEST="${MANIFESTS[$i]}"
        local LABEL="${LABELS[$i]}"

        if [ ! -f "$CURRENT_MANIFEST" ]; then
            echo "Warning: Manifest not found for $LABEL at $CURRENT_MANIFEST"
            continue
        fi

        echo "Adding manifest for: $LABEL (version: $SERVICE_VERSION)"
        echo "" >> "$OUT_FILE"
        echo "# === $LABEL ===" >> "$OUT_FILE"

        if [ -n "$REGISTRY_URL" ] && [ "$SHOULD_REPLACE" = "true" ]; then
            local TMP; TMP=$(mktemp)
            # Do not rewrite payment A/B service.version — v350.9 / v350.10
            # are the Buttercup demo versions APM uses to split errors.
            # stitch's numeric regex used to turn 1.7.2-a/b into the shop tag.
            sed -e "s|ghcr.io/[^/]*/[^/]*|${REGISTRY_URL}|g" \
                -e "s|app.kubernetes.io/version: [0-9][0-9.]*[^\"[:space:]]*|app.kubernetes.io/version: ${SERVICE_VERSION}|g" \
                "$CURRENT_MANIFEST" > "$TMP"
            apply_image_versions "$TMP"
            cat "$TMP" >> "$OUT_FILE"
            rm -f "$TMP"
        elif [ "$SHOULD_REPLACE" = "false" ]; then
            cat "$CURRENT_MANIFEST" >> "$OUT_FILE"
        else
            sed -e "s|app.kubernetes.io/version: [0-9][0-9.]*[^\"[:space:]]*|app.kubernetes.io/version: ${SERVICE_VERSION}|g" \
                "$CURRENT_MANIFEST" >> "$OUT_FILE"
        fi

        echo "" >> "$OUT_FILE"
        echo "---" >> "$OUT_FILE"
        FOUND_COUNT=$((FOUND_COUNT + 1))
    done

    return 0
}

# ============================================================
# Function: stitch_flagd_config
# Special handling for flagd-config ConfigMap from JSON source
# ============================================================
stitch_flagd_config() {
    local OUT_FILE="$1"
    local FLAGD_JSON="src/flagd/demo.flagd.json"
    local FLAGD_PVC="src/flagd-config/flagd-config-k8s.yaml"

    if [ ! -f "$FLAGD_JSON" ]; then
        echo "Warning: Flagd JSON not found at $FLAGD_JSON"
        return 1
    fi

    echo "Adding manifest for: flagd-config (version: $VERSION)"
    echo "  (using src/flagd/demo.flagd.json as single source)"
    echo "" >> "$OUT_FILE"
    echo "# === flagd-config ===" >> "$OUT_FILE"

    # Add PVC from flagd-config-k8s.yaml
    if [ -f "$FLAGD_PVC" ]; then
        cat "$FLAGD_PVC" >> "$OUT_FILE"
    fi

    # Generate ConfigMap with embedded JSON
    cat >> "$OUT_FILE" << 'CONFIGMAP_HEADER'
apiVersion: v1
kind: ConfigMap
metadata:
  name: flagd-config
  labels:
    app.kubernetes.io/part-of: opentelemetry-demo
data:
  demo.flagd.json: |
CONFIGMAP_HEADER
    sed 's/^/    /' "$FLAGD_JSON" >> "$OUT_FILE"

    echo "" >> "$OUT_FILE"
    echo "---" >> "$OUT_FILE"
    return 0
}

# ============================================================
# Function: stitch_manifest
# Stitch a list of services into an output file
# Args: output_file service1 service2 ...
# ============================================================
stitch_manifest() {
    local OUT_FILE="$1"
    shift
    local SERVICES=("$@")

    local FOUND=0
    local MISSING=()

    for SERVICE in "${SERVICES[@]}"; do
        if [ "$SERVICE" = "payment" ]; then
            stitch_payment "$OUT_FILE"
            FOUND=$((FOUND + 1))
        elif [ "$SERVICE" = "flagd-config" ]; then
            if stitch_flagd_config "$OUT_FILE"; then
                FOUND=$((FOUND + 1))
            else
                MISSING+=("$SERVICE")
            fi
        else
            if stitch_service "$SERVICE" "$OUT_FILE"; then
                FOUND=$((FOUND + 1))
            else
                MISSING+=("$SERVICE")
            fi
        fi
    done

    echo ""
    echo "  Services found: $FOUND"
    echo "  Services missing: ${#MISSING[@]}"
    if [ ${#MISSING[@]} -gt 0 ]; then
        for SERVICE in "${MISSING[@]}"; do
            echo "    - $SERVICE"
        done
    fi
}

# ============================================================
# Function: create_manifest_header
# Create the header comment block for a manifest file
# ============================================================
create_manifest_header() {
    local OUT_FILE="$1"
    local LABEL="$2"

    cat > "$OUT_FILE" << EOF
# Splunk Astronomy Shop Kubernetes Manifest${LABEL:+ - ${LABEL}}
# Version: $VERSION
# Generated on: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# This manifest combines service deployments for the Splunk Astronomy Shop
# Services are defined in services.yaml
---
EOF
}

# ============================================================
# Build filename helper
# ============================================================
build_filename() {
    local GROUP_SUFFIX="$1"
    local FILENAME="splunk-astronomy-shop-${VERSION}"
    if [ "$DIAB_SCENARIO" = "diab" ]; then
        FILENAME="${FILENAME}-diab"
    fi
    if [ -n "$GROUP_SUFFIX" ]; then
        FILENAME="${FILENAME}-${GROUP_SUFFIX}"
    fi
    if [ -n "$EXTRA_SUFFIX" ]; then
        FILENAME="${FILENAME}${EXTRA_SUFFIX}"
    fi
    echo "$OUTPUT_DIR/${FILENAME}.yaml"
}

# ============================================================
# MAIN: Stitch all manifests
# ============================================================

echo ""
echo "Reading services from services.yaml..."
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required to parse services.yaml"
    exit 1
fi

# --- Main manifest (services with no group) ---
echo ""
echo "=========================================="
echo "Building MAIN manifest"
echo "=========================================="

MAIN_SERVICES=()
for svc in $(python3 .github/scripts/get-services.py --manifest); do MAIN_SERVICES+=("$svc"); done

# Add ingress if DIAB scenario is enabled
if [ "$DIAB_SCENARIO" = "diab" ]; then
    echo "DIAB Scenario enabled - adding ingress to manifest"
    MAIN_SERVICES+=("ingress")
fi

MAIN_FILE=$(build_filename "")
create_manifest_header "$MAIN_FILE" ""
echo "Output: $MAIN_FILE"
echo "Services: ${#MAIN_SERVICES[@]}"
stitch_manifest "$MAIN_FILE" "${MAIN_SERVICES[@]}"

# --- Group manifests (lambda, dc-shim, etc.) ---
GROUPS_STR=$(python3 .github/scripts/get-services.py --groups)
for GROUP in $GROUPS_STR; do
    [ -z "$GROUP" ] && continue
    echo ""
    echo "=========================================="
    echo "Building ${GROUP} manifest"
    echo "=========================================="

    GROUP_SERVICES_STR=$(python3 .github/scripts/get-services.py --group "$GROUP")
    GROUP_SERVICES=()
    for svc in $GROUP_SERVICES_STR; do GROUP_SERVICES+=("$svc"); done

    GROUP_FILE=$(build_filename "$GROUP")
    create_manifest_header "$GROUP_FILE" "$GROUP"
    echo "Output: $GROUP_FILE"
    echo "Services: ${#GROUP_SERVICES[@]}"
    stitch_manifest "$GROUP_FILE" "${GROUP_SERVICES[@]}"
done

# --- Summary ---
echo ""
echo "=========================================="
echo "Manifest stitching complete!"
echo "=========================================="
echo "Version: $VERSION"
if [ "$DIAB_SCENARIO" = "diab" ]; then
    echo "Scenario: DIAB (includes ingress)"
fi
if [ -n "$EXTRA_SUFFIX" ]; then
    echo "Suffix: $EXTRA_SUFFIX"
fi
if [ -n "$REGISTRY_URL" ]; then
    echo "Registry: $REGISTRY_URL ($REGISTRY_ENV)"
fi

echo ""
echo "Generated manifests:"
echo "  Main: $MAIN_FILE"
for GROUP in $GROUPS_STR; do
    echo "  ${GROUP}: $(build_filename "$GROUP")"
done

echo ""
echo "To add a new service, edit services.yaml in the repository root."
