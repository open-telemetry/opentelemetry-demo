# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

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

EXPOSE ${MCP_PORT}

CMD ["python", "run.py"]
