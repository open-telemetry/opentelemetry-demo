# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/node:22-slim AS builder

WORKDIR /app

COPY ./src/flagd-ui/package.json package.json
COPY ./src/flagd-ui/package-lock.json package-lock.json

RUN npm ci

COPY ./src/flagd-ui/src/ src/

COPY ./src/flagd-ui/next.config.mjs next.config.mjs
COPY ./src/flagd-ui/postcss.config.mjs postcss.config.mjs
COPY ./src/flagd-ui/tsconfig.json tsconfig.json
COPY ./src/flagd-ui/tailwind.config.ts tailwind.config.ts

RUN npm run build

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/nodejs22-debian12:nonroot

ENV PORT=4000

WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static .next/static

EXPOSE ${PORT}

CMD ["server.js"]
