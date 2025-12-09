#!/bin/bash -e

# Usage:
#   ./build.sh <version> [-cc]

if [ -z "$1" ]; then
  echo "❌ Error: No version provided."
  echo "Usage: $0 <version> [-cc]"
  exit 1
fi

VERSION="$1"
CACHE_OPTION=""

# Check if the second arg is -cc
if [[ "$2" == "-cc" ]]; then
  CACHE_OPTION="--no-cache"
fi

# Registry and image configuration
REGISTRY="ghcr.io"
NAMESPACE="splunk/opentelemetry-demo"
LOAD_GEN_IMAGE="${REGISTRY}/${NAMESPACE}/otel-shop-dc-load-generator:${VERSION}"

# Build load generator
LOAD_GEN_DOCKER_CMD=(
  docker buildx build $CACHE_OPTION
  --platform=linux/amd64,linux/arm64
  --build-arg VERSION="$VERSION"
  -t "$LOAD_GEN_IMAGE"
  -f ./load-generator/Dockerfile
  --push
)
LOAD_GEN_DOCKER_CMD+=( . )

# Execute the builds
echo "Building load generator..."
"${LOAD_GEN_DOCKER_CMD[@]}"

echo "Load generator: ${LOAD_GEN_IMAGE}"