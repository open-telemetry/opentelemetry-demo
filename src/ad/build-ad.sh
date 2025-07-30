#!/bin/bash -e

# Usage:
#   ./build.sh <version> [-cc] [RUM_TOKEN] [RUM_REALM] [RUM_APP_NAME] [RUM_ENV] [RUM_URL_PREFIX]

if [ -z "$1" ]; then
  echo "❌ Error: No version provided."
  echo "Usage: $0 <version> [-cc] "
  exit 1
fi

VERSION="$1"
CACHE_OPTION=""

# Check if the second arg is -cc
if [[ "$2" == "-cc" ]]; then
  CACHE_OPTION="--no-cache"
  # Shift all remaining args so $2 becomes RUM_TOKEN
  shift
fi

# Move two directories up 

cd "$(dirname "$0")/../.."

# Build command
DOCKER_CMD=(
  docker buildx build $CACHE_OPTION
  --platform=linux/amd64,linux/arm64
  --build-arg VERSION="$VERSION"
  -t ghcr.io/splunk/opentelemetry-demo/otel-ad:"$VERSION"
  --push
  -f src/ad/Dockerfile
)


# Add build context
DOCKER_CMD+=( . )

# Execute the build
"${DOCKER_CMD[@]}"