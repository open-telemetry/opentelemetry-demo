# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/node:22 AS builder

WORKDIR /usr/src/app/

COPY ./src/payment/package.json package.json
COPY ./src/payment/package-lock.json package-lock.json

RUN npm ci --omit=dev && chmod -R go+r node_modules/@splunk/otel

# -----------------------------------------------------------------------------

FROM docker.io/library/node:22

WORKDIR /usr/src/app/

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /usr/src/app/node_modules/ node_modules/

COPY ./pb/demo.proto demo.proto

COPY ./src/payment/charge.js charge.js
COPY ./src/payment/index.js index.js
COPY ./src/payment/logger.js logger.js
COPY ./src/payment/opentelemetry.js opentelemetry.js

# Set ownership for non-root user
RUN chown -R appuser:appuser /usr/src/app

EXPOSE ${PAYMENT_PORT}

# Switch to non-root user
USER appuser

#CMD ["node", "-r @splunk/otel/instrument index.js"]
CMD ["--require=./opentelemetry.js", "index.js"]