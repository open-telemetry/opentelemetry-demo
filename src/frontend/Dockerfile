# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/node:22-slim AS builder

WORKDIR /app

COPY ./src/frontend/package.json package.json
COPY ./src/frontend/package-lock.json package-lock.json

RUN npm ci

COPY ./src/frontend/components/ components/
COPY ./src/frontend/gateways/ gateways/
COPY ./src/frontend/pages/ pages/
COPY ./src/frontend/protos/ protos/
COPY ./src/frontend/providers/ providers/
COPY ./src/frontend/services/ services/
COPY ./src/frontend/styles/ styles/
COPY ./src/frontend/types/ types/

COPY ./src/frontend/utils/enums/ utils/enums/
COPY ./src/frontend/utils/telemetry/ utils/telemetry/
COPY ./src/frontend/utils/imageLoader.js utils/imageLoader.js
COPY ./src/frontend/utils/logger.js utils/logger.js
COPY ./src/frontend/utils/Request.ts utils/Request.ts
COPY ./src/frontend/utils/userAttributes.ts utils/userAttributes.ts

COPY ./src/frontend/next.config.js next.config.js
COPY ./src/frontend/tsconfig.json tsconfig.json

RUN npm run build

# Inject sourceMapId into built JavaScript files
# This is done at build time so files already have sourceMapId when deployed
RUN npx @splunk/rum-cli sourcemaps inject \
    --path ".next/static" || echo "⚠️  Sourcemap injection skipped (non-fatal)"

# -----------------------------------------------------------------------------

FROM docker.io/library/node:22-slim AS deps

WORKDIR /app

COPY ./src/frontend/package.json package.json
COPY ./src/frontend/package-lock.json package-lock.json

RUN npm install  @splunk/rum-cli

RUN npm ci --omit=dev

# -----------------------------------------------------------------------------

#FROM gcr.io/distroless/nodejs22-debian12:nonroot
FROM node:22-slim

WORKDIR /app

COPY --from=builder /app/.next/standalone/ ./
COPY --from=builder /app/.next/static/ .next/static/

COPY --from=deps /app/node_modules/ node_modules/

COPY ./src/frontend/public/ public/

# Copy logger utility needed by Instrumentation.js
COPY ./src/frontend/utils/logger.js utils/logger.js

COPY ./src/frontend/utils/telemetry/Instrumentation.js Instrumentation.js

# Copy startup script for sourcemap upload and app start
COPY ./src/frontend/start.sh start.sh
RUN chmod +x start.sh

EXPOSE ${FRONTEND_PORT}

# Use NODE_OPTIONS to ensure instrumentation loads before server starts
ENV NODE_OPTIONS="--require ./Instrumentation.js"

# Use startup script instead of directly starting node
CMD ["./start.sh"]
#ENTRYPOINT ["tail", "-f", "/dev/null"] 