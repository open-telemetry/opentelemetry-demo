# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/node:26.4.0-slim@sha256:a1d9d671994fc2d26e297ac56b4b1522a8bc7fa71c43b14cd1b1fe6c5116f7dc AS builder

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
COPY ./src/frontend/utils/Request.ts utils/Request.ts

COPY ./src/frontend/next.config.js next.config.js
COPY ./src/frontend/tsconfig.json tsconfig.json

RUN npm run build

# -----------------------------------------------------------------------------

FROM docker.io/library/node:26.4.0-slim@sha256:a1d9d671994fc2d26e297ac56b4b1522a8bc7fa71c43b14cd1b1fe6c5116f7dc AS deps

WORKDIR /app

COPY ./src/frontend/package.json package.json
COPY ./src/frontend/package-lock.json package-lock.json

RUN npm ci --omit=dev

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/nodejs24-debian13:nonroot@sha256:ed5e65a1036b505c9e5abf0d0412ce0f70be1b812630bbbbaf49ce47edc7a513

WORKDIR /app

COPY --from=builder /app/.next/standalone/ ./
COPY --from=builder /app/.next/static/ .next/static/

COPY --from=deps /app/node_modules/ node_modules/

COPY ./src/frontend/public/ public/

COPY ./src/frontend/utils/telemetry/Instrumentation.js Instrumentation.js

EXPOSE ${FRONTEND_PORT}

CMD ["--require=./Instrumentation.js", "server.js"]
