# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Two-stage build: Generate service-centric Markdown with Weaver, then serve with mkdocs

# Stage 1: Generate Markdown files from telemetry schema using Weaver
FROM docker.io/otel/weaver:v0.25.1@sha256:9ad46ca9cd4fa5974b121f886aa3e9946a8ef8ea905001a96c018d21f9db87ca AS registry-builder

WORKDIR /home/weaver

# Copy the telemetry schema and templates, owned by the running user
COPY --chown=weaver:weaver telemetry-schema ./telemetry-schema
COPY --chown=weaver:weaver src/telemetry-docs/templates ./templates

RUN /weaver/weaver registry generate \
    --registry=./telemetry-schema \
    --templates=./templates \
    markdown \
    ./docs

RUN /weaver/weaver registry package \
    --registry=./telemetry-schema \
    --resolved-schema-uri=https://opentelemetry.io/schemas/1.40.0 \
    --output=./docs/schema \
    --v2

# Stage 2: Build static site
FROM docker.io/library/python:3.14.7-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52 AS site-builder

WORKDIR /app

COPY src/telemetry-docs/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/telemetry-docs/mkdocs.yml /app/mkdocs-base.yml
COPY --from=registry-builder /home/weaver/docs /app/docs

RUN mv /app/docs/mkdocs.yml /app/mkdocs.yml && \
    mkdocs build --clean

# Stage 3: Serve with nginx (tiny!)
FROM docker.io/nginxinc/nginx-unprivileged:1.31.2-alpine3.23-otel@sha256:1490cbf02ddba36ae75ef947b570166c805a178898ebfbc3bb889e7580820052

USER 101

COPY --from=site-builder /app/site /static
COPY src/telemetry-docs/nginx.conf.template /nginx.conf.template

ARG TELEMETRY_DOCS_PORT=8000
EXPOSE ${TELEMETRY_DOCS_PORT}

STOPSIGNAL SIGQUIT

# Start nginx
CMD ["/bin/sh" , "-c" , "envsubst '$OTEL_COLLECTOR_HOST $OTEL_COLLECTOR_PORT_GRPC $OTEL_SERVICE_NAME $TELEMETRY_DOCS_PORT' < /nginx.conf.template > /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
