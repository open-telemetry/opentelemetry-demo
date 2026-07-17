# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Two-stage build: Generate service-centric Markdown with Weaver, then serve with mkdocs

# Stage 1: Generate Markdown files from telemetry schema using Weaver
FROM docker.io/otel/weaver:v0.24.2@sha256:d1fb16d279f39810c340fbbf1cf9e5e995a3a9cefa531938e9012437e3bc00c1 AS registry-builder

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
FROM docker.io/library/python:3.14.6-slim-bookworm@sha256:86f975aca15cf04a40b399eebede9aea7c82eae084d1f1a0a6ef6bcaae871a30 AS site-builder

WORKDIR /app

COPY src/telemetry-docs/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/telemetry-docs/mkdocs.yml /app/mkdocs-base.yml
COPY --from=registry-builder /workspace/docs /app/docs

RUN mv /app/docs/mkdocs.yml /app/mkdocs.yml && \
    mkdocs build --clean

# Stage 3: Serve with nginx (tiny!)
FROM docker.io/nginxinc/nginx-unprivileged:1.31.2-alpine3.23-otel@sha256:1490cbf02ddba36ae75ef947b570166c805a178898ebfbc3bb889e7580820052

USER 101

COPY --from=site-builder /app/site /static
COPY src/telemetry-docs/nginx.conf.template /nginx.conf.template

EXPOSE ${TELEMETRY_DOCS_PORT}

STOPSIGNAL SIGQUIT

# Start nginx
CMD ["/bin/sh" , "-c" , "envsubst '$OTEL_COLLECTOR_HOST $OTEL_COLLECTOR_PORT_GRPC $OTEL_SERVICE_NAME $TELEMETRY_DOCS_PORT' < /nginx.conf.template > /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
