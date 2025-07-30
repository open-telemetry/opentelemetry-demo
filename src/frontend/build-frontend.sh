#!/bin/bash -e

# Usage:
#   ./build.sh <version> [-cc] [RUM_TOKEN] [RUM_REALM] [RUM_APP_NAME] [RUM_ENV] [RUM_URL_PREFIX]

if [ -z "$1" ]; then
  echo "❌ Error: No version provided."
  echo "Usage: $0 <version> [-cc] [RUM_TOKEN] [RUM_REALM] [RUM_APP_NAME] [RUM_ENV] [RUM_URL_PREFIX]"
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

RUM_TOKEN="$2"
RUM_REALM="$3"
RUM_APP_NAME="$4"
RUM_ENV="$5"
RUM_URL_PREFIX="$6"

if [ -n "$RUM_TOKEN" ]; then
  echo "🔍 RUM_TOKEN provided, checking required positional arguments..."

  # Validate additional required arguments if RUM_TOKEN is provided
  if [ -z "$RUM_REALM" ] || [ -z "$RUM_APP_NAME" ] || [ -z "$RUM_ENV" ] || [ -z "$RUM_URL_PREFIX" ]; then
    echo "❌ Error: Missing arguments. When RUM_TOKEN is provided, you must also provide:"
    echo "Usage: $0 <version> [-cc] <RUM_TOKEN> <RUM_REALM> <RUM_APP_NAME> <RUM_ENV> <RUM_URL_PREFIX>"
    exit 1
  fi

  echo "✅ All required RUM arguments provided."
fi

# Move two directories up from src/frontend
cd "$(dirname "$0")/../.."

# Build command
DOCKER_CMD=(
  docker buildx build $CACHE_OPTION
  --platform=linux/amd64,linux/arm64
  --build-arg VERSION="$VERSION"
  -t ghcr.io/splunk/opentelemetry-demo/otel-frontend:"$VERSION"
  --push
  -f src/frontend/Dockerfile
)

# Conditionally add RUM build args
if [ -n "$RUM_TOKEN" ]; then
  DOCKER_CMD+=( 
    --build-arg RUM_TOKEN="$RUM_TOKEN"
    --build-arg RUM_REALM="$RUM_REALM"
    --build-arg RUM_APP_NAME="$RUM_APP_NAME"
    --build-arg RUM_ENV="$RUM_ENV"
    --build-arg RUM_URL_PREFIX="$RUM_URL_PREFIX"
  )
else
  echo "ℹ️ RUM_TOKEN not provided; skipping rum-cli sourcemap upload during build."
fi

# Add build context
DOCKER_CMD+=( . )

# Execute the build
"${DOCKER_CMD[@]}"