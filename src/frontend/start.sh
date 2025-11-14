#!/bin/bash
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Startup script for frontend service
# 1. Upload sourcemaps to Splunk RUM (if configured)
# 2. Start the Next.js application with OpenTelemetry instrumentation

set -e

echo "🚀 Starting frontend service..."

# Upload sourcemaps if RUM credentials are provided
# Note: API_TOKEN must be an API token with RUM ingest permissions, not the RUM token
if [ -n "$API_TOKEN" ] && [ -n "$SPLUNK_RUM_REALM" ] && [ -n "$SPLUNK_APP_NAME" ]; then
  echo "📤 Uploading sourcemaps to Splunk RUM..."
  echo "   Realm: $SPLUNK_RUM_REALM"
  echo "   App: $SPLUNK_APP_NAME"
  echo "   Version: ${SPLUNK_APP_VERSION:-latest}"
  echo "   Note: sourceMapId was injected during Docker build"

  # Upload sourcemaps (injection already done at build time)
  echo "📤 Uploading sourcemaps..."
  npx @splunk/rum-cli sourcemaps upload \
    --path ".next/static" \
    --realm "$SPLUNK_RUM_REALM" \
    --token "$API_TOKEN" \
    --app-name "$SPLUNK_APP_NAME" \
    --app-version "${SPLUNK_APP_VERSION:-latest}" || {
      echo "⚠️  Warning: Sourcemap upload failed, but continuing with startup"
    }

  echo "✅ Sourcemap processing completed"
else
  echo "ℹ️  Skipping sourcemap upload (API_TOKEN not provided)"
  echo "    Note: Use API_TOKEN (API token with RUM ingest permissions), not SPLUNK_RUM_TOKEN"
fi

# Start the application with Node.js
# NODE_OPTIONS is already set in Dockerfile to load Instrumentation.js
echo "🌐 Starting Next.js server..."
exec node server.js
