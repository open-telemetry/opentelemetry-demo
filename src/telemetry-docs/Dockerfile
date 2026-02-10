# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Two-stage build: Generate service-centric Markdown with Weaver, then serve with mkdocs

# Stage 1: Generate Markdown files from telemetry schema using Weaver
FROM docker.io/otel/weaver:v0.21.2 AS registry-builder

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

# Generate fully resolved schema as JSON
RUN /weaver/weaver registry resolve \
    --registry=/workspace/telemetry-schema \
    --format=json \
    --output=/workspace/docs/schema.json

# Stage 2: Build static site
FROM python:3.14-slim-bookworm AS site-builder

WORKDIR /app

RUN pip install --no-cache-dir mkdocs mkdocs-material

COPY src/telemetry-docs/mkdocs.yml /app/mkdocs-base.yml
COPY --from=registry-builder /workspace/docs /app/docs

RUN mv /app/docs/mkdocs.yml /app/mkdocs.yml && \
    mkdocs build --clean

# Stage 3: Serve with nginx (tiny!)
FROM docker.io/nginxinc/nginx-unprivileged:1.29-alpine3.23-otel

USER 101

COPY --from=site-builder /app/site /static
COPY src/telemetry-docs/nginx.conf.template /nginx.conf.template

EXPOSE ${TELEMETRY_DOCS_PORT}

STOPSIGNAL SIGQUIT

# Start nginx
CMD ["/bin/sh" , "-c" , "envsubst '$OTEL_COLLECTOR_HOST $OTEL_COLLECTOR_PORT_GRPC $OTEL_SERVICE_NAME $TELEMETRY_DOCS_PORT' < /nginx.conf.template > /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
