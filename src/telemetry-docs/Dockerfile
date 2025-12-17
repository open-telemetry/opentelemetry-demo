# Two-stage build: Generate service-centric Markdown with Weaver, then serve with mkdocs

# Stage 1: Generate Markdown files from telemetry schema using Weaver
FROM otel/weaver:latest AS registry-builder

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

# Stage 2: Serve documentation with mkdocs
FROM python:3.11-slim

WORKDIR /app

# Install mkdocs and theme
RUN pip install --no-cache-dir mkdocs mkdocs-material

# Copy base mkdocs configuration (inherited by generated mkdocs.yml)
COPY src/telemetry-docs/mkdocs.yml /app/mkdocs-base.yml

# Copy generated documentation
COPY --from=registry-builder /workspace/docs /app/docs

# Put mkdocs.yml with dynamic navigation into the app root
RUN mv /app/docs/mkdocs.yml /app/mkdocs.yml

# Expose port for mkdocs
EXPOSE ${TELEMETRY_DOCS_PORT}

# Serve documentation
CMD ["sh", "-c", "mkdocs serve --dev-addr 0.0.0.0:${TELEMETRY_DOCS_PORT}"]
