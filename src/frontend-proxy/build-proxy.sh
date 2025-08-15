#!/bin/bash -e

# Usage:
#   ./build.sh <version> [-cc] 

if [ -z "$1" ]; then
  echo "❌ Error: No version provided."
  echo "Usage: $0 <version> [-cc] "
  exit 
fi

VERSION="$1"
CACHE_OPTION=""

# Check if the second arg is -cc
if [[ "$2" == "-cc" ]]; then
  CACHE_OPTION="--no-cache"
  # Shift all remaining args so $2 becomes RUM_TOKEN
  shift
fi
URL_PREFIX="$6"


# Move two directories up from src/recomndation
cd "$(dirname "$0")/../.."

# Build command
DOCKER_CMD=(
  docker buildx build
  --platform=linux/amd64,linux/arm64
  $CACHE_OPTION
  --build-arg VERSION="$VERSION"
  -t ghcr.io/splunk/opentelemetry-demo/otel-frontend-proxy:"$VERSION"
  --push
  -f src/frontend-proxy/Dockerfile
)

# Add build context
DOCKER_CMD+=( . )

# Execute the build
"${DOCKER_CMD[@]}"