# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Two-stage build: Generate service-centric Markdown with Weaver, then serve with mkdocs

# Stage 1: Generate Markdown files from telemetry schema using Weaver
FROM docker.io/otel/weaver:v0.23.0@sha256:7984ecb55b859eb3034ae9d836c4eeda137e2bdd0873b7ba2bb6c3d24d6ff457 AS registry-builder

WORKDIR /workspace

# Copy the telemetry schema
COPY telemetry-schema /workspace/telemetry-schema

# Copy the Weaver templates
COPY src/telemetry-docs/templates /workspace/templates

# Generate service-centric pages and mkdocs.yml using Weaver
RUN /weaver/weaver registry generate \
    --registry=/workspace/telemetry-schema \
    --templates=/workspace/templates \
    markdown \
    /workspace/docs

# Generate packaged resolved schema
RUN /weaver/weaver registry package \
    --registry=/workspace/telemetry-schema \
    --resolved-schema-uri=https://opentelemetry.io/schemas/1.40.0 \
    --output=/workspace/docs/schema \
    --v2

# Stage 2: Build static site
FROM docker.io/library/python:3.14.5-slim-bookworm@sha256:a9bee15510a364124aa24692899d269835683b883de42f7ebec8c293cf679ccb AS site-builder

WORKDIR /app

COPY src/telemetry-docs/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/telemetry-docs/mkdocs.yml /app/mkdocs-base.yml
COPY --from=registry-builder /workspace/docs /app/docs

RUN mv /app/docs/mkdocs.yml /app/mkdocs.yml && \
    mkdocs build --clean

# Stage 3: Serve with nginx (tiny!)
FROM docker.io/nginxinc/nginx-unprivileged:1.31.1-alpine3.23-otel@sha256:74e4659d671745bead1c3afbad7ef4a040e512bd3a144468f8c4607bc01dc49d

USER 101

COPY --from=site-builder /app/site /static
COPY src/telemetry-docs/nginx.conf.template /nginx.conf.template

EXPOSE ${TELEMETRY_DOCS_PORT}

STOPSIGNAL SIGQUIT

# Start nginx
CMD ["/bin/sh" , "-c" , "envsubst '$OTEL_COLLECTOR_HOST $OTEL_COLLECTOR_PORT_GRPC $OTEL_SERVICE_NAME $TELEMETRY_DOCS_PORT' < /nginx.conf.template > /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
