# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/mcp/requirements.txt .

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/mcp/src src
COPY src/shared/tools.py src/mcp_server
COPY src/mcp/run.py .

ARG MCP_PORT=8011
EXPOSE ${MCP_PORT}

CMD ["python", "run.py"]
