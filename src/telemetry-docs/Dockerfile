# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Two-stage build: Generate service-centric Markdown with Weaver, then serve with mkdocs

# Stage 1: Generate Markdown files from telemetry schema using Weaver
FROM docker.io/otel/weaver:v0.26.1@sha256:9094862c0ab261bdbcb079bb981f9a573b3659b130a6d2ab8616eca6ba37aaec AS registry-builder

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
FROM docker.io/library/python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS site-builder

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
