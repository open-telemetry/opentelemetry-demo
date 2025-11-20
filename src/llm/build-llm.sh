#!/bin/bash -e

# Usage:
#   ./build-llm.sh <version> [-cc]

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

# Move two directories up from src/llm
cd "$(dirname "$0")/../.."

echo "Building llm service version: $VERSION"
echo "Build options: ${CACHE_OPTION:-default caching enabled}"

# Build without push first
DOCKER_CMD=(
  docker buildx build
  --platform=linux/amd64,linux/arm64
  $CACHE_OPTION
  --build-arg VERSION="$VERSION"
  -t ghcr.io/splunk/opentelemetry-demo/otel-llm-shop:"$VERSION"
  --load
  -f src/llm/Dockerfile
  .
)

echo "Executing build command..."
if ! "${DOCKER_CMD[@]}"; then
  echo "❌ Error: Docker build failed"
  exit 1
fi

echo "✅ Build successful"

# Verify image exists locally
if ! docker image inspect ghcr.io/splunk/opentelemetry-demo/otel-llm-shop:"$VERSION" > /dev/null 2>&1; then
  echo "❌ Error: Built image not found locally"
  exit 1
fi

echo "✅ Image verified locally"

# Push the image
echo "Pushing image to registry..."
if ! docker push ghcr.io/splunk/opentelemetry-demo/otel-llm-shop:"$VERSION"; then
  echo "❌ Error: Push failed. Check your registry authentication."
  exit 1
fi

echo "✅ Successfully pushed ghcr.io/splunk/opentelemetry-demo/otel-llm-shop:$VERSION"
